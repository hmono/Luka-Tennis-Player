/** Durable acceptance is next-hop queue acceptance, never operator delivery. */
export interface InboxEvent { event_id: string; message: string }
export interface InboxAck { accepted: true; event_id: string; duplicate: boolean }
export interface SqlGuard { sql: string; bindings: unknown[] }
export class InboxError extends Error {
  constructor(public readonly code: string) { super(code); }
}
export function canonicalEvent(event: InboxEvent): string {
  if (typeof event.event_id !== 'string' || typeof event.message !== 'string' ||
      [...event.event_id].length < 1 || [...event.event_id].length > 256 ||
      [...event.message].length < 1 || [...event.message].length > 4096) {
    throw new InboxError('invalid_event');
  }
  const value = JSON.stringify({ event_id: event.event_id, message: event.message });
  if (new TextEncoder().encode(value).byteLength > 8192) throw new InboxError('invalid_size');
  return value;
}

/** Trusted SQL guard permits a watchdog lease and episode to share this batch.
 * Capacity is enforced by the migration's BEFORE INSERT trigger. A conflict
 * violates NOT NULL, rolling back the ENTIRE batch, including episode changes.
 */
export function enqueueStatement(db: D1Database, event_id: string, message: string,
  now: number, guard?: SqlGuard): D1PreparedStatement {
  const canonical = canonicalEvent({ event_id, message });
  return db.prepare(`INSERT INTO ops_events
    (event_id,canonical_payload,payload_bytes,state,accepted_at,due_at)
    SELECT ?,?,?,'pending',?,? WHERE ${guard?.sql ?? '1'}
    ON CONFLICT(event_id) DO UPDATE SET canonical_payload=
      CASE WHEN ops_events.canonical_payload=excluded.canonical_payload
      THEN ops_events.canonical_payload ELSE NULL END`)
    .bind(event_id, canonical, new TextEncoder().encode(canonical).byteLength,
      now, now, ...(guard?.bindings ?? []));
}

export interface InboxLease extends InboxEvent {
  token: string; attempts: number; leaseUntil: number;
}
export interface AttemptOutcome {
  accepted: boolean; errorCode?: string; retryAfterMs?: number;
}
export interface InboxRepositoryOptions {
  maxAttempts?: number; leaseMs?: number; maxConcurrency?: number;
  baseBackoffMs?: number; maxBackoffMs?: number;
}
export interface InboxStatus {
  persisted_events: number; pending_forwarding: number; quarantined_events: number;
  leased_events: number; dedup_tombstones: number; retained_payload_bytes: number;
  audit_rows: number; forwarding_failures: number; forwarding_attempts: number;
  oldest_pending_at: number | null; last_successful_forward: number | null;
  last_attempt_at: number | null; max_events: number; max_pending: number;
  max_payload_bytes: number; oldest_pending_age: number; progress_age: number | null;
  age_unit: 'milliseconds'; operator_delivered: 'unknown';
}
export class InboxRepository {
  readonly maxAttempts: number;
  readonly leaseMs: number;
  readonly maxConcurrency: number;
  readonly baseBackoffMs: number;
  readonly maxBackoffMs: number;
  constructor(readonly db: D1Database, options: InboxRepositoryOptions = {}) {
    this.maxAttempts = options.maxAttempts ?? 12;
    this.leaseMs = options.leaseMs ?? 30_000;
    this.maxConcurrency = options.maxConcurrency ?? 4;
    this.baseBackoffMs = options.baseBackoffMs ?? 60_000;
    this.maxBackoffMs = options.maxBackoffMs ?? 3_600_000;
    if (![this.maxAttempts, this.leaseMs, this.maxConcurrency, this.baseBackoffMs,
      this.maxBackoffMs].every(Number.isSafeInteger) || this.maxAttempts < 1 ||
      this.maxAttempts > 100 || this.leaseMs < 100 || this.leaseMs > 300_000 ||
      this.maxConcurrency < 1 || this.maxConcurrency > 4 || this.baseBackoffMs < 1 ||
      this.maxBackoffMs < this.baseBackoffMs || this.maxBackoffMs > 86_400_000) {
      throw new InboxError('invalid_repository_config');
    }
  }
  async accept(event: InboxEvent, now = Date.now()): Promise<InboxAck> {
    const canonical = canonicalEvent(event);
    try {
      // Prior read belongs to the same transaction as insert/read: simultaneous
      // same-ID requests obtain one new acceptance and identical replay acks.
      const result = await this.db.batch([
        this.db.prepare('SELECT event_id FROM ops_events WHERE event_id=?').bind(event.event_id),
        enqueueStatement(this.db, event.event_id, event.message, now),
        this.db.prepare('SELECT canonical_payload FROM ops_events WHERE event_id=?').bind(event.event_id),
      ]);
      if (result.some((item) => !item.success) ||
          (result[2].results[0] as { canonical_payload?: string } | undefined)?.canonical_payload !== canonical) {
        throw new InboxError('storage_unavailable');
      }
      return { accepted: true, event_id: event.event_id, duplicate: result[0].results.length > 0 };
    } catch (error) {
      // Classify without returning SQL, upstream details or event bodies.
      let prior: { canonical_payload: string } | null;
      try {
        prior = await this.db.prepare('SELECT canonical_payload FROM ops_events WHERE event_id=?')
          .bind(event.event_id).first<{ canonical_payload: string }>();
      } catch { throw new InboxError('storage_unavailable'); }
      if (prior && prior.canonical_payload !== canonical) throw new InboxError('event_id_conflict');
      if (String(error).includes('inbox_capacity')) throw new InboxError('inbox_capacity');
      throw new InboxError('storage_unavailable');
    }
  }
  async claimDue(now = Date.now()): Promise<InboxLease | null> {
    const token = crypto.randomUUID();
    const until = now + this.leaseMs;
    const results = await this.db.batch([
      // Interrupted final attempts become visible quarantine; none disappear.
      this.db.prepare(`INSERT INTO ops_inbox_audit(event_id,at,action,attempt,error_code)
        SELECT event_id,?,'quarantined',attempts,'attempt_budget_exhausted' FROM ops_events
        WHERE state IN ('pending','leased') AND attempts>=? AND coalesce(lease_until,0)<=?`)
        .bind(now, this.maxAttempts, now),
      this.db.prepare(`UPDATE ops_events SET state='quarantined',lease_token=NULL,
        lease_until=NULL,last_error='attempt_budget_exhausted' WHERE state IN ('pending','leased')
        AND attempts>=? AND coalesce(lease_until,0)<=?`).bind(this.maxAttempts, now),
      this.db.prepare(`UPDATE ops_forward_slots SET lease_token=?,lease_until=?
        WHERE slot=(SELECT slot FROM ops_forward_slots WHERE slot<? AND lease_until<=?
        ORDER BY slot LIMIT 1) AND EXISTS(SELECT 1 FROM ops_events
        WHERE state IN ('pending','leased') AND due_at<=? AND coalesce(lease_until,0)<=? AND attempts<?)`)
        .bind(token, until, this.maxConcurrency, now, now, now, this.maxAttempts),
      this.db.prepare(`UPDATE ops_events SET state='leased',lease_token=?,lease_until=?,
        attempts=attempts+1,last_attempt_at=?,due_at=? WHERE event_id=(
        SELECT event_id FROM ops_events WHERE state IN ('pending','leased') AND due_at<=?
        AND coalesce(lease_until,0)<=? AND attempts<? ORDER BY due_at,accepted_at,event_id LIMIT 1)
        AND EXISTS(SELECT 1 FROM ops_forward_slots WHERE lease_token=?)`)
        .bind(token, until, now, until, now, now, this.maxAttempts, token),
      this.db.prepare(`INSERT INTO ops_inbox_audit(event_id,at,action,attempt)
        SELECT event_id,?,'attempt',attempts FROM ops_events WHERE lease_token=?`).bind(now, token),
      this.db.prepare('SELECT canonical_payload,attempts,lease_until FROM ops_events WHERE lease_token=?').bind(token),
    ]);
    if (results.some((row) => !row.success)) throw new InboxError('storage_unavailable');
    const row = results[5].results[0] as { canonical_payload: string; attempts: number; lease_until: number } | undefined;
    return row ? { ...JSON.parse(row.canonical_payload) as InboxEvent, token,
      attempts: row.attempts, leaseUntil: row.lease_until } : null;
  }
  async finishAttempt(lease: InboxLease, outcome: AttemptOutcome, now = Date.now()): Promise<boolean> {
    const accepted = outcome.accepted === true;
    const exhausted = lease.attempts >= this.maxAttempts;
    const state = accepted ? 'forwarded' : exhausted ? 'quarantined' : 'pending';
    const error = accepted ? null : sanitizeError(outcome.errorCode);
    const backoff = Math.min(this.maxBackoffMs, this.baseBackoffMs * 2 ** Math.min(lease.attempts - 1, 20));
    const retryAfter = Math.min(this.maxBackoffMs, Math.max(0, outcome.retryAfterMs ?? 0));
    const result = await this.db.batch([
      this.db.prepare(`INSERT INTO ops_inbox_audit(event_id,at,action,attempt,error_code)
        SELECT event_id,?,?,attempts,? FROM ops_events WHERE event_id=? AND state='leased'
        AND lease_token=? AND lease_until>?`).bind(now, state, error, lease.event_id, lease.token, now),
      this.db.prepare(`UPDATE ops_events SET state=?,due_at=?,lease_token=NULL,lease_until=NULL,
        forwarded_at=?,last_error=? WHERE event_id=? AND state='leased' AND lease_token=? AND lease_until>?
        RETURNING event_id`)
        .bind(state, now + Math.max(backoff, retryAfter), accepted ? now : null,
          error, lease.event_id, lease.token, now),
      this.db.prepare('UPDATE ops_forward_slots SET lease_token=NULL,lease_until=0 WHERE lease_token=?').bind(lease.token),
    ]);
    if (result.some((item) => !item.success)) throw new InboxError('storage_unavailable');
    // D1 meta.changes includes trigger writes; RETURNING counts only fenced events.
    return result[1].results.length === 1;
  }
  async status(now = Date.now()): Promise<InboxStatus> {
    const result = await this.db.batch<Record<string, number | null>>([
      this.db.prepare(`SELECT events AS persisted_events,pending AS pending_forwarding,
        quarantined AS quarantined_events,leased AS leased_events,tombstones AS dedup_tombstones,
        payload_bytes AS retained_payload_bytes,audit_rows,failures AS forwarding_failures,
        attempts AS forwarding_attempts,last_successful_forward,last_attempt_at
        FROM ops_inbox_totals WHERE id=1`),
      this.db.prepare(`SELECT min(accepted_at) AS oldest_pending_at FROM (
        SELECT accepted_at FROM (SELECT accepted_at FROM ops_events WHERE state='pending' ORDER BY accepted_at LIMIT 1)
        UNION ALL SELECT accepted_at FROM (SELECT accepted_at FROM ops_events WHERE state='leased' ORDER BY accepted_at LIMIT 1)
        UNION ALL SELECT accepted_at FROM (SELECT accepted_at FROM ops_events WHERE state='quarantined' ORDER BY accepted_at LIMIT 1))`),
      this.db.prepare('SELECT max_events,max_pending,max_payload_bytes FROM ops_inbox_limits WHERE id=1'),
    ]);
    if (result.some((item) => !item.success) || !result[0].results[0] || !result[2].results[0]) throw new InboxError('storage_unavailable');
    const row = { ...result[0].results[0], ...result[1].results[0] } as Record<string, number | null>;
    return { ...row, ...result[2].results[0],
      oldest_pending_age: row.oldest_pending_at === null ? 0 : Math.max(0, now - Number(row.oldest_pending_at)),
      progress_age: row.last_successful_forward === null ? null : Math.max(0, now - Number(row.last_successful_forward)),
      age_unit: 'milliseconds', operator_delivered: 'unknown' } as InboxStatus;
  }
  async retainForwarded(before: number, now = Date.now()): Promise<number> {
    const result = await this.db.batch([
      this.db.prepare(`INSERT INTO ops_inbox_audit(event_id,at,action,attempt)
        SELECT event_id,?,'tombstone',attempts FROM ops_events
        WHERE state='forwarded' AND forwarded_at<? AND tombstone=0`).bind(now, before),
      this.db.prepare(`UPDATE ops_events SET tombstone=1 WHERE state='forwarded'
        AND forwarded_at<? AND tombstone=0 RETURNING event_id`).bind(before),
    ]);
    if (result.some((item) => !item.success)) throw new InboxError('storage_unavailable');
    return result[1].results.length;
  }
}
function sanitizeError(code?: string): string {
  return code && /^(http_[1-5][0-9]{2}|timeout|invalid_ack|response_too_large|transport_error|invalid_forward_config)$/.test(code)
    ? code : 'transport_error';
}
