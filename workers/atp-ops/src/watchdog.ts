import { GitHubActionsClient, type ActionsClient, type WorkflowRun } from "./github_client";
import { GitHubError, type AppCredentials } from "./github_auth";
import { enqueueStatement } from "./inbox_repository";

export type IncidentCode = "MISSED_RUN" | "RUN_FAILURE" | "SCHEDULER_DELAY" | "RUN_DURATION" | "WORKFLOW_DISABLED" | "MONITOR_UNAVAILABLE";
export interface Incident { code: IncidentCode; scope: string; slot: string; message: string; recoverable: boolean }
export interface WatchdogConfig {
  watchdogEnabled: boolean; deliveryEnabled: boolean; recoveryEnabled: boolean;
  repository: string; workflow: string; credentials: AppCredentials;
}
export interface WatchdogOptions {
  now?: number; scheduledTime?: number; client?: ActionsClient;
  /** Synthetic crash injection; no production handler supplies this hook. */
  afterReservation?: (slot: string, attempt: number) => Promise<void>;
}
export interface WatchdogReport {
  checked_at: string; workflow_state: string; released: boolean; incidents: Incident[];
  recoveries: number; status: "ok" | "disabled" | "busy" | "stale" | "state_unavailable";
}
interface Episode { scope: string; code: string; generation: number; event_id: string; active: number }
const MINUTE = 60_000;
const GRACE = 90 * MINUTE;
const LEASE = 5 * MINUTE;

export function pollSlots(now: number, days = 2): number[] {
  const result: number[] = [];
  for (let offset = 0; offset <= days; offset++) {
    const day = new Date(now - offset * 86_400_000);
    for (const hour of [12, 18]) result.push(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), hour, 17));
    if (day.getUTCDay() === 1) result.push(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 12));
  }
  return [...new Set(result)].filter(slot => slot <= now).sort((a, b) => a - b);
}

export function assessRuns(now: number, runs: WorkflowRun[]): Incident[] {
  const due = pollSlots(now).filter(slot => slot + GRACE <= now);
  if (!due.length) return [];
  const slot = due[due.length - 1];
  const next = pollSlots(slot + 86_400_000).find(candidate => candidate > slot) ?? slot + 86_400_000;
  const sid = new Date(slot).toISOString();
  const eligible = runs.filter(run => run.head_branch === "main" &&
    (run.event === "schedule" || (run.event === "workflow_dispatch" && run.display_title === "ATP rankings collect-and-deliver")) &&
    Date.parse(run.created_at) >= slot && Date.parse(run.created_at) < next);
  const incident = (code: IncidentCode, message: string, recoverable = false): Incident =>
    ({ code, scope: code, slot: sid, message, recoverable });
  if (!eligible.length) return [incident("MISSED_RUN", `No production main ranking run observed for ${sid} after 90-minute grace; source status unknown.`, true)];
  const latest = eligible.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at) || b.id - a.id)[0];
  const started = Date.parse(latest.run_started_at || latest.created_at);
  if (!Number.isFinite(started) || (latest.status === "completed" && !Number.isFinite(Date.parse(latest.updated_at ?? ""))))
    throw new GitHubError("run_metadata_invalid");
  const incidents: Incident[] = [];
  if (started - slot > 60 * MINUTE) incidents.push(incident("SCHEDULER_DELAY", `Production ranking run for ${sid} started over 60 minutes late.`));
  const end = latest.status === "completed" ? Date.parse(latest.updated_at!) : now;
  if (end - started > 20 * MINUTE) incidents.push(incident("RUN_DURATION", `Production ranking run for ${sid} exceeded 20 minutes; source status unknown.`));
  if (latest.status === "completed" && latest.conclusion !== "success")
    incidents.push(incident("RUN_FAILURE", `Production ranking run for ${sid} failed; source status unknown.`, true));
  return incidents;
}

const monitorIncident = (): Incident => ({ code: "MONITOR_UNAVAILABLE", scope: "MONITOR_UNAVAILABLE", slot: "",
  message: "GitHub metadata is unavailable; scheduler and source status unknown.", recoverable: false });

function stateWrite(db: D1Database, key: string, value: string, owner: string): D1PreparedStatement {
  return db.prepare(`INSERT INTO watchdog_state(key,value) SELECT ?,? WHERE EXISTS
    (SELECT 1 FROM watchdog_state WHERE key='cycle_lease' AND value=?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value`).bind(key, value, owner);
}

/** Public to exercise the durable reservation independently under concurrent schedulers. */
export async function reserveDispatch(db: D1Database, slot: string, now: number, owner: string): Promise<number | null> {
  const slotTime = Date.parse(slot);
  if (!Number.isFinite(slotTime) || now < slotTime || now - slotTime > 6 * 60 * MINUTE) return null;
  // One SQL mutation is the budget authority; concurrent observations cannot over-reserve.
  const result = await db.prepare(`INSERT INTO watchdog_dispatches(slot,attempt,reserved_at,result)
    SELECT ?,COALESCE(MAX(attempt),0)+1,?,'reserved' FROM watchdog_dispatches WHERE slot=?
    HAVING COUNT(*)<2 AND (MAX(reserved_at) IS NULL OR MAX(reserved_at)<=?)
      AND EXISTS(SELECT 1 FROM watchdog_state WHERE key='cycle_lease' AND value=?)
    RETURNING attempt`).bind(slot, now, slot, now - 30 * MINUTE, owner).first<{ attempt: number }>();
  return result?.attempt ?? null;
}

async function reconcile(db: D1Database, incidents: Incident[], observable: Set<string>, now: number, owner: string): Promise<void> {
  const rows = await db.prepare("SELECT scope,code,generation,event_id,active FROM watchdog_episodes").all<Episode>();
  const previous = new Map(rows.results.map(row => [row.scope, row]));
  const statements: D1PreparedStatement[] = [];
  const guard = { sql: "EXISTS(SELECT 1 FROM watchdog_state WHERE key='cycle_lease' AND value=?)", bindings: [owner] };
  for (const item of incidents) {
    const old = previous.get(item.scope);
    if (old?.active) {
      statements.push(db.prepare(`UPDATE watchdog_episodes SET last_seen_at=? WHERE scope=? AND ${guard.sql}`).bind(now, item.scope, owner));
      continue;
    }
    const generation = (old?.generation ?? 0) + 1;
    const eventId = `scheduler:${item.scope}:${generation}`;
    statements.push(db.prepare(`INSERT INTO watchdog_episodes(scope,code,generation,event_id,active,opened_at,last_seen_at,closed_at)
      SELECT ?,?,?,?,1,?,?,NULL WHERE ${guard.sql}
      ON CONFLICT(scope) DO UPDATE SET code=excluded.code,generation=excluded.generation,event_id=excluded.event_id,
        active=1,opened_at=excluded.opened_at,last_seen_at=excluded.last_seen_at,closed_at=NULL`)
      .bind(item.scope, item.code, generation, eventId, now, now, owner));
    statements.push(enqueueStatement(db, eventId, item.message, now, guard));
  }
  const active = new Set(incidents.map(item => item.scope));
  for (const row of previous.values()) {
    if (!row.active || !observable.has(row.scope) || active.has(row.scope)) continue;
    statements.push(db.prepare(`UPDATE watchdog_episodes SET active=0,closed_at=?,last_seen_at=? WHERE scope=? AND ${guard.sql}`)
      .bind(now, now, row.scope, owner));
    statements.push(enqueueStatement(db, `scheduler:RECOVERED:${row.scope}:${row.generation}`,
      `Ranking scheduler ${row.code} episode recovered; source freshness and message delivery are assessed separately.`, now, guard));
  }
  // A capacity/conflict error in the inbox aborts every episode change as well.
  if (statements.length) await db.batch(statements);
}

export async function runWatchdog(db: D1Database, config: WatchdogConfig, options: WatchdogOptions = {}): Promise<WatchdogReport> {
  const now = options.now ?? Date.now();
  if (!Number.isFinite(now)) throw new Error("clock_invalid");
  const released = config.watchdogEnabled === true && config.deliveryEnabled === true;
  const report: WatchdogReport = { checked_at: new Date(now).toISOString(), workflow_state: "unknown", released,
    incidents: [], recoveries: 0, status: released ? "ok" : "disabled" };
  // Before initial release there is no token grant, D1 mutation, dispatch or alert.
  if (!released) return report;
  const owner = JSON.stringify({ id: crypto.randomUUID(), expires: now + LEASE });
  let acquired = false;
  try {
    const claim = await db.prepare(`INSERT INTO watchdog_state(key,value) VALUES('cycle_lease',?)
      ON CONFLICT(key) DO UPDATE SET value=excluded.value WHERE CAST(json_extract(watchdog_state.value,'$.expires') AS INTEGER)<=?`)
      .bind(owner, now).run();
    if (!claim.meta.changes) { report.status = "busy"; return report; }
    acquired = true;
    const previousCheck = await db.prepare("SELECT value FROM watchdog_state WHERE key='last_check'").first<{ value: string }>();
    if (previousCheck && now <= Number(previousCheck.value)) { report.status = "stale"; return report; }
    await stateWrite(db, "last_started", String(now), owner).run();
    let observable = new Set<string>(["MONITOR_UNAVAILABLE"]);
    let client = options.client;
    const cronDelayed = (previousCheck && now - Number(previousCheck.value) > 20 * MINUTE) ||
      (options.scheduledTime !== undefined && now - options.scheduledTime > 2 * MINUTE);
    try {
      const backoff = await db.prepare("SELECT value FROM watchdog_state WHERE key='api_retry_at'").first<{ value: string }>();
      if (backoff && now < Number(backoff.value)) throw new GitHubError("github_backoff", 0, Number(backoff.value));
      client ??= new GitHubActionsClient(config.repository, config.workflow, config.credentials, config.recoveryEnabled === true);
      const inspection = await client.inspect(now);
      report.workflow_state = inspection.state;
      if (inspection.state === "active") {
        report.incidents = assessRuns(now, inspection.runs);
        observable = new Set(["MISSED_RUN", "RUN_FAILURE", "RUN_DURATION", "SCHEDULER_DELAY", "WORKFLOW_DISABLED", "MONITOR_UNAVAILABLE"]);
      } else {
        report.incidents = [{ code: "WORKFLOW_DISABLED", scope: "WORKFLOW_DISABLED", slot: "",
          message: "Ranking workflow is disabled; source status unknown. Initial release is required.", recoverable: false }];
        observable.add("WORKFLOW_DISABLED");
      }
      await db.batch([stateWrite(db, "api_retry_at", "0", owner), stateWrite(db, "last_observed", String(now), owner)]);
    } catch (error) {
      report.workflow_state = "unknown";
      report.incidents = [monitorIncident()];
      const retryAt = error instanceof GitHubError && error.retryAt ? error.retryAt : now + 10 * MINUTE;
      await stateWrite(db, "api_retry_at", String(retryAt), owner).run();
    }
    observable.add("SCHEDULER_DELAY:cron");
    if (cronDelayed) report.incidents.push({ code: "SCHEDULER_DELAY", scope: "SCHEDULER_DELAY:cron", slot: "",
      message: "Watchdog cron heartbeat is missing or delayed; independent supervision must assess its own availability.", recoverable: false });
    await reconcile(db, report.incidents, observable, now, owner);
    for (const item of report.incidents) {
      if (!item.recoverable || config.recoveryEnabled !== true || report.workflow_state !== "active") continue;
      const attempt = await reserveDispatch(db, item.slot, now, owner);
      if (attempt === null) continue;
      report.recoveries++;
      await options.afterReservation?.(item.slot, attempt);
      let result = "unknown_or_failed";
      try {
        await client!.dispatch(); result = "accepted";
      } catch (error) {
        if (error instanceof GitHubError && error.retryAt) await stateWrite(db, "api_retry_at", String(error.retryAt), owner).run();
      }
      await db.prepare("UPDATE watchdog_dispatches SET result=? WHERE slot=? AND attempt=?").bind(result, item.slot, attempt).run();
    }
    await db.batch([stateWrite(db, "last_check", String(now), owner),
      // Older slots cannot be dispatched after the monotonic watermark advances.
      db.prepare(`DELETE FROM watchdog_dispatches WHERE reserved_at<? AND EXISTS
        (SELECT 1 FROM watchdog_state WHERE key='cycle_lease' AND value=?)`).bind(now - 86_400_000, owner)]);
  } catch {
    report.status = "state_unavailable";
    report.incidents = [monitorIncident()];
  } finally {
    if (acquired) {
      try { await db.prepare("DELETE FROM watchdog_state WHERE key='cycle_lease' AND value=?").bind(owner).run(); }
      catch { report.status = "state_unavailable"; }
    }
  }
  return report;
}

export async function watchdogHealth(db: D1Database, now = Date.now()): Promise<Record<string, unknown>> {
  const rows = await db.prepare("SELECT key,value FROM watchdog_state WHERE key IN ('last_check','last_started','last_observed','api_retry_at')").all<{ key: string; value: string }>();
  const values = Object.fromEntries(rows.results.map(row => [row.key, Number(row.value)]));
  const episodes = await db.prepare("SELECT scope,code,generation,opened_at,last_seen_at FROM watchdog_episodes WHERE active=1 ORDER BY scope").all();
  const reservations = await db.prepare("SELECT COUNT(*) AS count FROM watchdog_dispatches").first<{ count: number }>();
  return { last_check: values.last_check ?? null, last_started: values.last_started ?? null,
    last_successful_observation: values.last_observed ?? null, api_retry_at: values.api_retry_at ?? null,
    heartbeat_age_ms: values.last_check === undefined ? null : Math.max(0, now - values.last_check),
    heartbeat_stale: values.last_check === undefined || now - values.last_check > 20 * MINUTE,
    active_episodes: episodes.results, dispatch_reservations: reservations?.count ?? 0 };
}
