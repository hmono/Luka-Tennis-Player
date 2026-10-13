import { env } from "cloudflare:workers";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { GitHubAppAuth, GitHubError, githubRequest, signAppJwt, type AppCredentials } from "../src/github_auth";
import { GitHubActionsClient, type ActionsClient, type WorkflowRun } from "../src/github_client";
import { assessRuns, pollSlots, reserveDispatch, runWatchdog, watchdogHealth, type WatchdogConfig } from "../src/watchdog";

const DB = env.DB as D1Database;
const now = Date.parse("2026-10-13T14:00:00Z");
const slot = "2026-10-13T12:17:00.000Z";
const emptyCredentials = { appId: "1", installationId: "2", privateKeyPem: "synthetic-unused" };
const config: WatchdogConfig = { watchdogEnabled: true, deliveryEnabled: true, recoveryEnabled: false,
  repository: "fixture/repository", workflow: "update_rankings.yml", credentials: emptyCredentials };
const run = (override: Partial<WorkflowRun> = {}): WorkflowRun => ({ id: 1, head_branch: "main", event: "schedule",
  display_title: "ATP rankings collect-and-deliver", created_at: slot, run_started_at: slot,
  updated_at: "2026-10-13T12:18:00Z", status: "completed", conclusion: "success", ...override });
const client = (state = "active", runs: WorkflowRun[] = []): ActionsClient => ({ inspect: vi.fn(async () => ({ state, runs })), dispatch: vi.fn(async () => {}) });
const json = (value: unknown, status = 200, headers?: HeadersInit) => new Response(JSON.stringify(value), { status, headers });
async function events(): Promise<{ event_id: string; state: string }[]> {
  return (await DB.prepare("SELECT event_id,state FROM ops_events ORDER BY event_id").all<{ event_id: string; state: string }>()).results;
}

describe("production ranking observation", () => {
  it("derives every daily and Monday slot for eight synthetic weeks without calendar input", () => {
    const start = Date.parse("2026-08-17T00:00:00Z");
    const end = start + 56 * 86_400_000 - 1;
    const slots = pollSlots(end, 56).filter(value => value >= start);
    expect(slots).toHaveLength(120);
    expect(slots.filter(value => new Date(value).getUTCMinutes() === 0)).toHaveLength(8);
  });
  it("ignores dry-run, branch development and title substrings", () => {
    for (const excluded of [run({ head_branch: "development" }), run({ event: "workflow_dispatch", display_title: "ATP rankings dry-run" }),
      run({ event: "workflow_dispatch", display_title: "ATP rankings collect-and-deliver dry-run" }), run({ event: "push" })]) {
      expect(assessRuns(now, [excluded]).map(item => item.code)).toEqual(["MISSED_RUN"]);
    }
    expect(assessRuns(now, [run({ event: "workflow_dispatch" })])).toEqual([]);
  });
  it("the next poll cannot mask a missing earlier slot", () => {
    expect(assessRuns(Date.parse("2026-10-13T18:30:00Z"), [run({ created_at: "2026-10-13T18:17:00Z" })])[0].code).toBe("MISSED_RUN");
  });
  it("detects failure, delayed start and excessive duration", () => {
    expect(assessRuns(now, [run({ conclusion: "failure" })]).map(item => item.code)).toEqual(["RUN_FAILURE"]);
    expect(assessRuns(now, [run({ run_started_at: "2026-10-13T13:18:00Z", updated_at: "2026-10-13T13:45:00Z" })])
      .map(item => item.code)).toEqual(["SCHEDULER_DELAY", "RUN_DURATION"]);
    expect(assessRuns(now, [run({ status: "in_progress" })]).map(item => item.code)).toEqual(["RUN_DURATION"]);
  });
  it("newer successful production runs supersede an earlier failure", () => {
    expect(assessRuns(now, [run({ conclusion: "failure" }), run({ id: 2, created_at: "2026-10-13T12:18:00Z" })])).toEqual([]);
  });
});

describe("D1 episodes, fencing and durable dispatches", () => {
  it("disabled gates have no D1 mutation or App/network activity", async () => {
    const api = client();
    for (const setting of [{ ...config, watchdogEnabled: false }, { ...config, deliveryEnabled: false }]) {
      expect((await runWatchdog(DB, setting, { now, client: api })).status).toBe("disabled");
    }
    expect(api.inspect).not.toHaveBeenCalled();
    expect(await events()).toEqual([]);
    expect((await DB.prepare("SELECT COUNT(*) AS n FROM watchdog_state").first<{ n: number }>())?.n).toBe(0);
  });
  it("eight weekly disable/recovery episodes remain distinct after restart", async () => {
    for (let week = 0; week < 8; week++) {
      const instant = now + week * 7 * 86_400_000;
      await runWatchdog(DB, config, { now: instant, client: client("disabled_manually") });
      // A fresh client simulates a new isolate; healthy observation uses that week's due slot.
      const due = pollSlots(instant + 600_000).filter(value => value + 5_400_000 <= instant + 600_000).at(-1)!;
      const healthy = run({ created_at: new Date(due).toISOString(), run_started_at: new Date(due).toISOString(), updated_at: new Date(due + 60_000).toISOString() });
      await runWatchdog(DB, config, { now: instant + 600_000, client: client("active", [healthy]) });
    }
    const ids = (await events()).map(row => row.event_id);
    expect(ids.filter(id => id.startsWith("scheduler:WORKFLOW_DISABLED:"))).toHaveLength(8);
    expect(ids.filter(id => id.startsWith("scheduler:RECOVERED:WORKFLOW_DISABLED:"))).toHaveLength(8);
  });
  it("persistent missing run with lost/repeated alerts never creates duplicate event IDs", async () => {
    for (const offset of [0, 600_000, 1_200_000, 1_800_000]) await runWatchdog(DB, config, { now: now + offset, client: client() });
    const rows = await events();
    expect(rows).toEqual([{ event_id: "scheduler:MISSED_RUN:1", state: "pending" }]);
    await runWatchdog(DB, config, { now: now + 2_400_000, client: client("active", [run()]) });
    expect((await events()).map(row => row.event_id)).toContain("scheduler:RECOVERED:MISSED_RUN:1");
  });
  it("disabled workflows never dispatch or enable", async () => {
    const api = client("disabled_manually");
    await runWatchdog(DB, { ...config, recoveryEnabled: true }, { now, client: api });
    expect(api.dispatch).not.toHaveBeenCalled();
    expect((await events())[0].event_id).toBe("scheduler:WORKFLOW_DISABLED:1");
  });
  it("API outage does not invent recovery of a pre-existing disable episode", async () => {
    await runWatchdog(DB, config, { now, client: client("disabled_manually") });
    const unavailable = { inspect: vi.fn(async () => { throw new Error("synthetic secret marker"); }), dispatch: vi.fn() };
    for (const offset of [600_000, 1_200_000, 1_800_000]) {
      const report = await runWatchdog(DB, config, { now: now + offset, client: unavailable });
      expect(JSON.stringify(report)).not.toContain("synthetic secret marker");
    }
    expect((await events()).map(row => row.event_id)).toEqual(["scheduler:MONITOR_UNAVAILABLE:1", "scheduler:WORKFLOW_DISABLED:1"]);
    await runWatchdog(DB, config, { now: now + 2_400_000, client: client("disabled_manually") });
    expect((await events()).filter(row => row.event_id.startsWith("scheduler:WORKFLOW_DISABLED"))).toHaveLength(1);
  });
  it("persists rate-limit cooldown across isolates and resumes without a new outage alert", async () => {
    const limited = { inspect: vi.fn(async () => { throw new GitHubError("github_http", 429, now + 1_800_000); }), dispatch: vi.fn() };
    await runWatchdog(DB, config, { now, client: limited });
    const recovered = client("active", [run()]);
    await runWatchdog(DB, config, { now: now + 600_000, client: recovered });
    expect(recovered.inspect).not.toHaveBeenCalled();
    await runWatchdog(DB, config, { now: now + 1_800_000, client: recovered });
    expect(recovered.inspect).toHaveBeenCalledTimes(1);
    expect((await events()).filter(row => row.event_id.startsWith("scheduler:MONITOR_UNAVAILABLE:"))).toHaveLength(1);
  });
  it("reserves at most twice per slot with thirty-minute cooldown despite dispatch errors", async () => {
    const api = client();
    api.dispatch = vi.fn(async () => { throw new Error("ambiguous"); });
    const enabled = { ...config, recoveryEnabled: true };
    for (const offset of [0, 600_000, 1_800_000, 3_600_000]) await runWatchdog(DB, enabled, { now: now + offset, client: api });
    expect(api.dispatch).toHaveBeenCalledTimes(2);
    const rows = await DB.prepare("SELECT attempt,result FROM watchdog_dispatches ORDER BY attempt").all();
    expect(rows.results).toEqual([{ attempt: 1, result: "unknown_or_failed" }, { attempt: 2, result: "unknown_or_failed" }]);
  });
  it("a crash after durable reservation consumes budget and never replays the POST", async () => {
    const api = client();
    const enabled = { ...config, recoveryEnabled: true };
    const crashed = await runWatchdog(DB, enabled, { now, client: api, afterReservation: async () => { throw new Error("synthetic crash"); } });
    expect(crashed.status).toBe("state_unavailable");
    expect(api.dispatch).not.toHaveBeenCalled();
    await runWatchdog(DB, enabled, { now: now + 600_000, client: api });
    expect(api.dispatch).not.toHaveBeenCalled();
    await runWatchdog(DB, enabled, { now: now + 1_800_000, client: api });
    expect(api.dispatch).toHaveBeenCalledTimes(1);
    expect((await DB.prepare("SELECT result FROM watchdog_dispatches WHERE attempt=1").first<{ result: string }>())?.result).toBe("reserved");
  });
  it("concurrent scheduler invocations serialize observation before dispatch", async () => {
    let release!: () => void;
    let inspecting!: () => void;
    const entered = new Promise<void>(resolve => { inspecting = resolve; });
    const hold = new Promise<void>(resolve => { release = resolve; });
    const api = client();
    api.inspect = vi.fn(async () => { inspecting(); await hold; return { state: "active", runs: [] }; });
    const first = runWatchdog(DB, { ...config, recoveryEnabled: true }, { now, client: api });
    await entered;
    const second = await runWatchdog(DB, { ...config, recoveryEnabled: true }, { now, client: api });
    expect(second.status).toBe("busy");
    release(); await first;
    expect(api.dispatch).toHaveBeenCalledTimes(1);
    expect(await events()).toHaveLength(1);
  });
  it("the reservation SQL independently rejects concurrent and unfenced writers", async () => {
    await DB.prepare("INSERT INTO watchdog_state VALUES('cycle_lease','fixture-owner')").run();
    const results = await Promise.all([reserveDispatch(DB, slot, now, "fixture-owner"), reserveDispatch(DB, slot, now, "fixture-owner")]);
    expect(results.filter(value => value !== null)).toHaveLength(1);
    expect(await reserveDispatch(DB, slot, now + 1_800_000, "expired-owner")).toBeNull();
  });
  it("expired lease takeover fences a stale observer's episodes and reservations", async () => {
    const api = client();
    api.inspect = vi.fn(async () => {
      await DB.prepare("UPDATE watchdog_state SET value=? WHERE key='cycle_lease'").bind(JSON.stringify({ id: "new-owner", expires: now + 1_000_000 })).run();
      return { state: "active", runs: [] };
    });
    await runWatchdog(DB, { ...config, recoveryEnabled: true }, { now, client: api });
    expect(await events()).toHaveLength(0);
    expect(api.dispatch).not.toHaveBeenCalled();
    expect((await DB.prepare("SELECT COUNT(*) AS n FROM watchdog_episodes").first<{ n: number }>())?.n).toBe(0);
  });
  it("inbox conflicting payload rolls back incident identity atomically", async () => {
    await DB.prepare(`INSERT INTO ops_events(event_id,canonical_payload,payload_bytes,state,accepted_at,due_at)
      VALUES('scheduler:MISSED_RUN:1','conflicting',11,'pending',?,?)`).bind(now, now).run();
    const report = await runWatchdog(DB, config, { now, client: client() });
    expect(report.status).toBe("state_unavailable");
    expect((await DB.prepare("SELECT COUNT(*) AS n FROM watchdog_episodes").first<{ n: number }>())?.n).toBe(0);
  });
  it("inbox capacity rejection rolls back the episode and blocks recovery dispatch", async () => {
    await DB.prepare("UPDATE ops_inbox_limits SET max_pending=1").run();
    await DB.prepare(`INSERT INTO ops_events(event_id,canonical_payload,payload_bytes,state,accepted_at,due_at)
      VALUES('existing','fixture',7,'pending',?,?)`).bind(now, now).run();
    const api = client();
    const report = await runWatchdog(DB, { ...config, recoveryEnabled: true }, { now, client: api });
    expect(report.status).toBe("state_unavailable");
    expect(api.dispatch).not.toHaveBeenCalled();
    expect((await DB.prepare("SELECT COUNT(*) AS n FROM watchdog_episodes").first<{ n: number }>())?.n).toBe(0);
    expect(await events()).toHaveLength(1);
  });
  it("missed/delayed cron appears in persistent health and recovers on the next tick", async () => {
    await runWatchdog(DB, config, { now, client: client("active", [run()]), scheduledTime: now - 180_000 });
    expect((await events()).map(row => row.event_id)).toContain("scheduler:SCHEDULER_DELAY:cron:1");
    await runWatchdog(DB, config, { now: now + 600_000, client: client("active", [run()]) });
    expect((await events()).map(row => row.event_id)).toContain("scheduler:RECOVERED:SCHEDULER_DELAY:cron:1");
    expect((await watchdogHealth(DB, now + 2_400_000)).heartbeat_stale).toBe(true);
  });
  it("monotonic watermark rejects stale replay after safe reservation cleanup", async () => {
    await runWatchdog(DB, config, { now, client: client() });
    const api = client();
    expect((await runWatchdog(DB, { ...config, recoveryEnabled: true }, { now: now - 600_000, client: api })).status).toBe("stale");
    expect(api.inspect).not.toHaveBeenCalled();
  });
});

describe("WebCrypto App authentication and bounded GitHub transport", () => {
  let keys: CryptoKeyPair;
  let credentials: AppCredentials;
  beforeAll(async () => {
    keys = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]) as CryptoKeyPair;
    const bytes = new Uint8Array(await crypto.subtle.exportKey("pkcs8", keys.privateKey) as ArrayBuffer);
    credentials = { ...emptyCredentials, privateKeyPem: `-----BEGIN PRIVATE KEY-----\n${btoa(String.fromCharCode(...bytes))}\n-----END PRIVATE KEY-----` };
  });
  it("signs an actual RS256 JWT with conservative claims and validates the signature", async () => {
    const jwt = await signAppJwt(credentials, now);
    const [header, claims, signature] = jwt.split(".");
    const decode = (part: string) => atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    expect(JSON.parse(decode(header))).toEqual({ alg: "RS256", typ: "JWT" });
    expect(JSON.parse(decode(claims))).toEqual({ iss: "1", iat: now / 1000 - 60, exp: now / 1000 + 540 });
    expect(await crypto.subtle.verify("RSASSA-PKCS1-v1_5", keys.publicKey,
      Uint8Array.from(decode(signature), c => c.charCodeAt(0)), new TextEncoder().encode(`${header}.${claims}`))).toBe(true);
  });
  it("converts a synthetic PKCS1 RSA private key before WebCrypto signing", async () => {
    const bytes = new Uint8Array(await crypto.subtle.exportKey("pkcs8", keys.privateKey) as ArrayBuffer);
    let offset = 0;
    const tlv = (): { start: number; end: number } => {
      offset++; let size = bytes[offset++];
      if (size & 128) { const count = size & 127; size = 0; for (let i = 0; i < count; i++) size = size * 256 + bytes[offset++]; }
      return { start: offset, end: offset + size };
    };
    tlv(); let field = tlv(); offset = field.end; field = tlv(); offset = field.end; field = tlv();
    const pkcs1 = bytes.slice(field.start, field.end);
    const pem = `-----BEGIN RSA PRIVATE KEY-----\n${btoa(String.fromCharCode(...pkcs1))}\n-----END RSA PRIVATE KEY-----`;
    expect((await signAppJwt({ ...credentials, privateKeyPem: pem }, now)).split(".")).toHaveLength(3);
  });
  it("downscopes each renewable token to one repository and Actions read", async () => {
    let instant = now;
    const fetcher = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect(JSON.parse(init!.body as string)).toEqual({ repositories: ["repository"], permissions: { actions: "read" } });
      return json({ token: `synthetic-token-${instant}`, expires_at: new Date(instant + 3_600_000).toISOString() });
    });
    const auth = new GitHubAppAuth(credentials, "fixture/repository", "read", fetcher, () => instant);
    for (let week = 0; week < 8; week++) { instant = now + week * 7 * 86_400_000; await auth.getToken(); }
    expect(fetcher).toHaveBeenCalledTimes(8);
    instant += 3_539_999; await auth.getToken(); expect(fetcher).toHaveBeenCalledTimes(8);
    instant++; await auth.getToken(); expect(fetcher).toHaveBeenCalledTimes(9);
  });
  it("rejects invalid grants and does not send a stale cached token", async () => {
    const fetcher = vi.fn(async () => json({ token: "", expires_at: new Date(now + 3_600_000).toISOString() }));
    const auth = new GitHubAppAuth(credentials, "fixture/repository", "read", fetcher, () => now);
    await expect(auth.getToken()).rejects.toMatchObject({ code: "installation_token_invalid" });
    await expect(auth.getToken()).rejects.toMatchObject({ code: "installation_token_invalid" });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it("renews at most once on a GET401 and never replays a dispatch POST401", async () => {
    let grants = 0; let gets = 0; let posts = 0;
    const fetcher = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).includes("access_tokens")) { grants++; return json({ token: `fixture-${grants}`, expires_at: new Date(now + 3_600_000).toISOString() }); }
      if (init?.method === "POST") { posts++; return json({}, 401); }
      gets++; if (gets === 1) return json({}, 401);
      if (String(url).includes("/runs?")) return json({ workflow_runs: [], total_count: 0 });
      return json({ state: "active" });
    });
    const api = new GitHubActionsClient("fixture/repository", "update_rankings.yml", credentials, true, fetcher, () => now);
    await api.inspect(now); expect(grants).toBe(2);
    await expect(api.dispatch()).rejects.toMatchObject({ status: 401 });
    expect(posts).toBe(1); expect(grants).toBe(2);
  });
  it("old histories are excluded, 500 relevant runs are allowed and overflow fails closed", async () => {
    let total = 500;
    const fetcher = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).includes("access_tokens")) return json({ token: "fixture", expires_at: new Date(now + 3_600_000).toISOString() });
      if (String(url).includes("/runs?")) {
        const query = new URL(String(url)).searchParams;
        expect(query.get("created")).toBe(`${new Date(now - 172_800_000).toISOString()}..${new Date(now).toISOString()}`);
        const page = Number(query.get("page"));
        return json({ total_count: total, workflow_runs: Array.from({ length: 100 }, (_, index) => run({ id: page * 100 + index })) });
      }
      return json({ state: "active" });
    });
    const api = new GitHubActionsClient("fixture/repository", "update_rankings.yml", credentials, false, fetcher, () => now);
    expect((await api.inspect(now)).runs).toHaveLength(500);
    total = 501; await expect(api.inspect(now)).rejects.toMatchObject({ code: "run_metadata_truncated" });
    await expect(api.dispatch()).rejects.toMatchObject({ code: "recovery_permission_required" });
  });
  it.each([403, 429])("%i creates a sanitized conservative cooldown", async status => {
    const fetcher = vi.fn(async () => json({ secret: "must-never-escape" }, status, { "retry-after": "1800" }));
    await expect(githubRequest(fetcher, "https://api.github.com/fixture", "synthetic-secret", now))
      .rejects.toMatchObject({ code: "github_http", status, retryAt: now + 1_800_000 });
  });
  it("a full deadline bounds a fetch that stalls before response headers", async () => {
    vi.useFakeTimers();
    try {
      const request = githubRequest(vi.fn(() => new Promise<Response>(() => {})), "https://api.github.com/fixture", "fixture", now, undefined, 100);
      const assertion = expect(request).rejects.toMatchObject({ code: "github_deadline" });
      await vi.advanceTimersByTimeAsync(100); await assertion;
    } finally { vi.useRealTimers(); }
  });
  it("a full deadline bounds a response whose body never completes", async () => {
    vi.useFakeTimers();
    try {
      const fetcher = vi.fn(async () => new Response(new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode("{")); } })));
      const request = githubRequest(fetcher, "https://api.github.com/fixture", "fixture", now, undefined, 100);
      const assertion = expect(request).rejects.toMatchObject({ code: "github_deadline" });
      await vi.advanceTimersByTimeAsync(100); await assertion;
    } finally { vi.useRealTimers(); }
  });
  it("rejects oversized response bodies and never follows redirects", async () => {
    const fetcher = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.redirect).toBe("error"); return new Response("x".repeat(2_000_001));
    });
    await expect(githubRequest(fetcher, "https://api.github.com/fixture", "fixture", now)).rejects.toMatchObject({ code: "github_body_limit" });
  });
});
