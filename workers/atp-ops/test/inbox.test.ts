import { env } from 'cloudflare:workers';
import { describe, expect, it, vi } from 'vitest';
import { handleInboxRequest } from '../src/inbox';
import { forwardDue } from '../src/forwarding';
import { canonicalEvent, enqueueStatement, InboxRepository } from '../src/inbox_repository';

const TOKEN = 'synthetic-inbox-token';
const SINK = 'https://synthetic-sink.invalid/events';
const event = (id = 'synthetic:event:1', message = 'synthetic message') => ({ event_id: id, message });
const repo = () => new InboxRepository(env.DB);
function request(payload: unknown, token = TOKEN) {
  return new Request('https://synthetic-inbox.invalid/events', { method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload) });
}
function sink(ack: unknown = { accepted: true, event_id: 'synthetic:event:1' }, status = 200) {
  return vi.fn(async () => Response.json(ack, { status })) as unknown as typeof fetch;
}
async function row(id = 'synthetic:event:1') {
  return env.DB.prepare('SELECT * FROM ops_events WHERE event_id=?').bind(id).first<Record<string, unknown>>();
}
const enabled = (fetcher: typeof fetch, now = () => 1000) => ({
  enabled: true, url: SINK, token: 'synthetic-sink-token', fetch: fetcher, now,
});

describe('durable synthetic inbox on local D1', () => {
  it('serializes simultaneous same-ID commits, acknowledges one creation, and rejects conflicts', async () => {
    const repository = repo();
    const acks = await Promise.all(Array.from({ length: 12 }, () => repository.accept(event(), 1000)));
    expect(acks.filter((ack) => !ack.duplicate)).toHaveLength(1);
    expect(acks.every((ack) => ack.accepted === true)).toBe(true);
    expect((await repository.status(2000)).persisted_events).toBe(1);
    const response = await handleInboxRequest(request(event(undefined, 'changed synthetic content')),
      { repository, token: TOKEN });
    expect(response.status).toBe(409);
    expect((await row())?.canonical_payload).toBe(canonicalEvent(event()));
  });

  it('commits before ack and recovers a lost ingress response across repository restart', async () => {
    const response = await handleInboxRequest(request({ ...event(), kind: 'ranking_operational' }),
      { repository: repo(), token: TOKEN });
    expect(response.status).toBe(200);
    // Do not consume the first ack: independent D1 read proves commit happened.
    expect((await row())?.state).toBe('pending');
    const replay = await handleInboxRequest(request(event()), { repository: repo(), token: TOKEN });
    expect(await replay.json()).toEqual({ accepted: true, event_id: event().event_id, duplicate: true });
    expect((await repo().status()).persisted_events).toBe(1);
  });

  it('never acknowledges storage rejection and rolls back episode/outbox batches at capacity', async () => {
    await env.DB.prepare('UPDATE ops_inbox_limits SET max_pending=1 WHERE id=1').run();
    await repo().accept(event(), 1000);
    await expect(env.DB.batch([
      env.DB.prepare("INSERT INTO watchdog_state(key,value) VALUES('synthetic:episode','opened')"),
      enqueueStatement(env.DB, 'synthetic:event:2', 'synthetic second event', 1001),
    ])).rejects.toThrow();
    expect(await env.DB.prepare("SELECT value FROM watchdog_state WHERE key='synthetic:episode'").first()).toBeNull();
    const full = await handleInboxRequest(request(event('synthetic:event:2')), { repository: repo(), token: TOKEN });
    expect(full.status).toBe(503);
    expect(await full.json()).toEqual({ error: 'inbox_capacity' });
    expect(await repo().accept(event(), 1002)).toMatchObject({ duplicate: true });
    expect(await row('synthetic:event:2')).toBeNull();
  });

  it('rolls back an episode on canonical conflict and fences stale watchdog writers', async () => {
    await repo().accept(event(), 1000);
    await expect(env.DB.batch([
      env.DB.prepare("INSERT INTO watchdog_state(key,value) VALUES('synthetic:episode','opened')"),
      enqueueStatement(env.DB, event().event_id, 'conflicting synthetic message', 1001),
    ])).rejects.toThrow();
    expect(await env.DB.prepare("SELECT value FROM watchdog_state WHERE key='synthetic:episode'").first()).toBeNull();
    await enqueueStatement(env.DB, 'synthetic:stale', 'synthetic stale event', 1001,
      { sql: 'EXISTS(SELECT 1 FROM watchdog_state WHERE key=? AND value=?)',
        bindings: ['synthetic:cycle_lease', 'stale-token'] }).run();
    expect(await row('synthetic:stale')).toBeNull();
  });

  it('fails closed on failed commit and on a response deadline with eventual commit', async () => {
    const storageFailure = { accept: vi.fn(async () => { throw new Error('synthetic commit failure'); }) } as unknown as InboxRepository;
    const failed = await handleInboxRequest(request(event()), { repository: storageFailure, token: TOKEN });
    expect(failed.status).toBe(503);
    expect(await failed.json()).toEqual({ error: 'storage_unavailable' });
    expect(await row()).toBeNull();
    let commit!: () => void;
    const gate = new Promise<void>((resolve) => { commit = resolve; });
    const repository = repo();
    const delayed = { accept: async (payload: ReturnType<typeof event>) => {
      await gate; return repository.accept(payload, 1000);
    } } as unknown as InboxRepository;
    const timeout = await handleInboxRequest(request(event()), { repository: delayed, token: TOKEN, requestDeadlineMs: 5 });
    expect(timeout.status).toBe(503);
    commit();
    await gate;
    // Await the delayed durable commit using the original pending acceptance.
    await repository.accept(event(), 1001);
    expect(await repo().accept(event())).toMatchObject({ duplicate: true });
  });

  it('authenticates health and ingress and bounds shape, UTF-8 bytes and partial bodies', async () => {
    expect((await handleInboxRequest(request(event(), 'synthetic wrong token'), { repository: repo(), token: TOKEN })).status).toBe(401);
    const health = new Request('https://synthetic-inbox.invalid/health', { headers: { Authorization: `Bearer ${TOKEN}` } });
    expect((await handleInboxRequest(health, { repository: repo(), token: TOKEN })).status).toBe(200);
    for (const payload of [null, [], 1, { event_id: 'x', message: '' }, event(undefined, 'é'.repeat(4096))]) {
      expect((await handleInboxRequest(request(payload), { repository: repo(), token: TOKEN })).status).toBe(400);
    }
    const stalled = new Request('https://synthetic-inbox.invalid/events', {
      method: 'POST', headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' },
      body: new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('{')); } }),
    });
    expect((await handleInboxRequest(stalled, { repository: repo(), token: TOKEN, bodyDeadlineMs: 5 })).status).toBe(408);
    expect((await repo().status()).persisted_events).toBe(0);
  });

  it('preserves Unicode across canonical forwarding', async () => {
    const payload = event(undefined, 'é'.repeat(2000));
    await repo().accept(payload, 1000);
    const fetcher = vi.fn(async (_url: unknown, init: RequestInit | undefined) => {
      expect(new TextEncoder().encode(String(init?.body)).byteLength).toBeLessThan(8192);
      expect(JSON.parse(String(init?.body))).toEqual(payload);
      expect(new Headers(init?.headers).get('Idempotency-Key')).toMatch(/^[0-9a-f]{64}$/);
      expect(init?.redirect).toBe('manual');
      return Response.json({ accepted: true, event_id: payload.event_id });
    }) as unknown as typeof fetch;
    expect(await forwardDue(repo(), enabled(fetcher))).toMatchObject({ forwarded: 1 });
  });

  it.each([{}, { accepted: false, event_id: 'synthetic:event:1' },
    { accepted: 1, event_id: 'synthetic:event:1' }, { accepted: true },
    { accepted: true, event_id: 'synthetic:wrong' }, null])('retains pending on invalid acknowledgment %j', async (ack) => {
    await repo().accept(event(), 1000);
    expect(await forwardDue(repo(), enabled(sink(ack)))).toMatchObject({ forwarded: 0, failures: 1 });
    expect(await row()).toMatchObject({ state: 'pending', attempts: 1, last_error: 'invalid_ack' });
    expect((await repo().status(2000)).forwarding_failures).toBe(1);
  });

  it.each([400, 409, 429, 503])('retains durable retries for HTTP %i with backoff', async (status) => {
    await repo().accept(event(), 1000);
    const fetcher = vi.fn(async () => Response.json({ error: 'synthetic rejection' }, {
      status, headers: { 'Retry-After': '120' },
    })) as unknown as typeof fetch;
    await forwardDue(repo(), enabled(fetcher));
    expect(await row()).toMatchObject({ state: 'pending', attempts: 1, due_at: 121000, last_error: `http_${status}` });
    expect(await forwardDue(repo(), enabled(fetcher, () => 2000))).toMatchObject({ attempted: 0 });
  });

  it('bounds hanging fetch and slow body deadlines and response bytes', async () => {
    await repo().accept(event(), 1000);
    const hanging = vi.fn(async () => new Promise<Response>(() => {})) as unknown as typeof fetch;
    await forwardDue(repo(), { ...enabled(hanging), timeoutMs: 5 });
    expect(await row()).toMatchObject({ state: 'pending', last_error: 'timeout' });
    await repo().accept(event('synthetic:drip'), 2000);
    const drip = vi.fn(async () => new Response(new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('{'));
    } }))) as unknown as typeof fetch;
    await forwardDue(repo(), { ...enabled(drip, () => 2000), timeoutMs: 5 });
    expect(await row('synthetic:drip')).toMatchObject({ state: 'pending', last_error: 'timeout' });
    await repo().accept(event('synthetic:large'), 3000);
    await forwardDue(repo(), { ...enabled(sink({ accepted: true, event_id: 'x', excess: 'x'.repeat(9000) }), () => 3000) });
    expect(await row('synthetic:large')).toMatchObject({ state: 'pending', last_error: 'response_too_large' });
  });

  it('makes progress beyond a poison queue head and quarantines exhausted work explicitly', async () => {
    const repository = new InboxRepository(env.DB, { maxAttempts: 2 });
    await repository.accept(event('synthetic:a-poison'), 1000);
    await repository.accept(event('synthetic:b-healthy'), 1001);
    const fetcher = vi.fn(async (_url: unknown, init: RequestInit | undefined) => {
      const payload = JSON.parse(String(init?.body));
      return payload.event_id.endsWith('a-poison') ? Response.json({}, { status: 400 }) : Response.json({ accepted: true, event_id: payload.event_id });
    }) as unknown as typeof fetch;
    expect(await forwardDue(repository, enabled(fetcher, () => 1001))).toMatchObject({ attempted: 2, forwarded: 1 });
    await forwardDue(repository, enabled(fetcher, () => 61001));
    expect(await row('synthetic:a-poison')).toMatchObject({ state: 'quarantined', attempts: 2 });
    const metrics = await new InboxRepository(env.DB).status(62000);
    expect(metrics).toMatchObject({ pending_forwarding: 1, quarantined_events: 1,
      oldest_pending_age: 61000, last_successful_forward: 1001, progress_age: 60999 });
  });

  it('bounds concurrent forwarding through durable slots and fences expired owners', async () => {
    for (let i = 0; i < 8; i++) await repo().accept(event(`synthetic:concurrent:${i}`), 1000);
    const claims = await Promise.all(Array.from({ length: 8 }, () => repo().claimDue(1000)));
    const active = claims.filter((claim) => claim !== null);
    expect(active).toHaveLength(4);
    expect(new Set(active.map((claim) => claim.event_id)).size).toBe(4);
    const original = active[0];
    expect(original).toBeTruthy();
    const replacement = await repo().claimDue(31000);
    expect(replacement).not.toBeNull();
    expect(await repo().finishAttempt(original!, { accepted: true }, 31000)).toBe(false);
    expect((await repo().status()).pending_forwarding).toBe(8);
    expect(await repo().finishAttempt(replacement!, { accepted: true }, 31001)).toBe(true);
  });

  it('replays after sink commit/ack loss and local mark failure with one durable sink event', async () => {
    await env.DB.exec('CREATE TABLE synthetic_sink_events(event_id TEXT PRIMARY KEY, canonical TEXT NOT NULL)');
    await repo().accept(event(), 1000);
    let calls = 0;
    const fetcher = vi.fn(async (_url: unknown, init: RequestInit | undefined) => {
      const payload = JSON.parse(String(init?.body));
      await env.DB.prepare('INSERT OR IGNORE INTO synthetic_sink_events(event_id,canonical) VALUES(?,?)')
        .bind(payload.event_id, String(init?.body)).run();
      if (++calls === 1) throw new Error('synthetic lost acknowledgment');
      return Response.json({ accepted: true, event_id: payload.event_id });
    }) as unknown as typeof fetch;
    await forwardDue(repo(), enabled(fetcher));
    expect(await row()).toMatchObject({ state: 'pending' });
    const broken = repo();
    vi.spyOn(broken, 'finishAttempt').mockRejectedValueOnce(new Error('synthetic local commit failure'));
    await expect(forwardDue(broken, enabled(fetcher, () => 61000))).rejects.toThrow('synthetic local commit failure');
    expect(await row()).toMatchObject({ state: 'leased', attempts: 2 });
    await forwardDue(repo(), enabled(fetcher, () => 91000));
    expect(await row()).toMatchObject({ state: 'forwarded', attempts: 3 });
    expect(await env.DB.prepare('SELECT count(*) AS count FROM synthetic_sink_events').first('count')).toBe(1);
    expect(calls).toBe(3);
  });

  it('counts interrupted final attempt as quarantined, retains it, and preserves audit', async () => {
    const repository = new InboxRepository(env.DB, { maxAttempts: 1 });
    await repository.accept(event(), 1000);
    await repository.claimDue(1000);
    expect(await new InboxRepository(env.DB, { maxAttempts: 1 }).claimDue(31000)).toBeNull();
    expect(await row()).toMatchObject({ state: 'quarantined', last_error: 'attempt_budget_exhausted' });
    expect((await repo().status(32000)).forwarding_failures).toBe(1);
  });

  it('retains exact replay tombstones and audit without deleting pending or growing past quota', async () => {
    await env.DB.prepare('UPDATE ops_inbox_limits SET max_events=2 WHERE id=1').run();
    await repo().accept(event(), 1000);
    await repo().accept(event('synthetic:pending'), 1000);
    await forwardDue(repo(), { ...enabled(sink()), maxBatch: 1 });
    expect(await repo().retainForwarded(2000, 2000)).toBe(1);
    expect(await row()).toMatchObject({ state: 'forwarded', tombstone: 1 });
    expect(await row('synthetic:pending')).toMatchObject({ state: 'pending', tombstone: 0 });
    expect(await repo().accept(event(), 3000)).toMatchObject({ duplicate: true });
    await expect(repo().accept(event(undefined, 'synthetic conflict'), 3000)).rejects.toThrow('event_id_conflict');
    await expect(repo().accept(event('synthetic:overflow'), 3000)).rejects.toThrow('inbox_capacity');
    await expect(env.DB.prepare('DELETE FROM ops_events WHERE event_id=?').bind(event().event_id).run()).rejects.toThrow();
    expect((await repo().status(3000)).dedup_tombstones).toBe(1);
    expect((await repo().status(3000)).audit_rows).toBeGreaterThanOrEqual(3);
  });

  it('gates forwarding off and rejects malformed configuration before any network call', async () => {
    await repo().accept(event(), 1000);
    const fetcher = sink();
    expect(await forwardDue(repo(), { ...enabled(fetcher), enabled: false })).toMatchObject({ disabled: true, attempted: 0 });
    for (const url of ['http://synthetic-sink.invalid', 'https://user:pass@synthetic-sink.invalid',
      'https://synthetic-sink.invalid/#fragment', 'https://synthetic-sink.invalid/\n']) {
      await expect(forwardDue(repo(), { ...enabled(fetcher), url })).rejects.toThrow('invalid_forward_config');
    }
    expect(fetcher).not.toHaveBeenCalled();
    expect(await row()).toMatchObject({ state: 'pending', attempts: 0 });
  });
});
