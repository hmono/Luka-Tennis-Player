import { env } from 'cloudflare:workers';
import { describe, it, expect, vi } from 'vitest';
import worker, { type Env } from '../src/index';
import { InboxRepository } from '../src/inbox_repository';
import { forwardDue } from '../src/forwarding';
import { runWatchdog, type WatchdogConfig } from '../src/watchdog';
import { type ActionsClient } from '../src/github_client';

const instant = Date.parse('2026-10-13T15:00:00Z');
const config: WatchdogConfig = {
  watchdogEnabled: true, deliveryEnabled: true, recoveryEnabled: false,
  repository: 'synthetic/repository', workflow: 'update_rankings.yml',
  credentials: { appId: '1', installationId: '2', privateKeyPem: 'synthetic-not-used' },
};
const disabled: ActionsClient = {
  inspect: async () => ({ state: 'disabled_manually', runs: [] }),
  dispatch: async () => { throw new Error('forbidden_dispatch'); },
};
function localEnv(): Env {
  return { DB: env.DB, GITHUB_REPOSITORY: 'synthetic/repository',
    GITHUB_WORKFLOW: 'update_rankings.yml', INBOX_TOKEN: 'synthetic-ingress',
    HEALTH_TOKEN: 'synthetic-health' };
}
function post(id: string, message = 'synthetic message', token = 'synthetic-ingress'): Request {
  return new Request('https://local.invalid/events', { method: 'POST',
    headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: JSON.stringify({ event_id: id, message }) });
}
const count = async (table: string) =>
  (await env.DB.prepare(`SELECT COUNT(*) AS n FROM ${table}`).first<{ n: number }>())!.n;

describe('integrated durable boundaries, entirely synthetic', () => {
  it('commits ingress before acknowledgment, survives lost acknowledgment and rejects changed content', async () => {
    const first = await worker.fetch(post('ingress-1'), localEnv());
    expect(first.status).toBe(200);
    // Caller never consumes first acknowledgment; retry reaches a new repository.
    const replay = await worker.fetch(post('ingress-1'), localEnv());
    expect(await replay.json()).toMatchObject({ accepted: true, duplicate: true, event_id: 'ingress-1' });
    expect(await count('ops_events')).toBe(1);
    expect((await worker.fetch(post('ingress-1', 'conflicting'), localEnv())).status).toBe(409);
  });

  it('separates administrative health credentials and rejects anonymous ingress', async () => {
    expect((await worker.fetch(post('unauthorized', 'x', ''), localEnv())).status).toBe(401);
    expect((await worker.fetch(post('health-token-cannot-write', 'x', 'synthetic-health'), localEnv())).status).toBe(401);
    expect((await worker.fetch(new Request('https://local.invalid/health', {
      headers: { authorization: 'Bearer synthetic-ingress' },
    }), localEnv())).status).toBe(401);
    const health = await worker.fetch(new Request('https://local.invalid/health', {
      headers: { authorization: 'Bearer synthetic-health' },
    }), localEnv());
    expect(health.status).toBe(503);
    expect(await health.json()).toMatchObject({ healthy: false, production_gates_open: false });
    expect(await count('ops_events')).toBe(0);
  });

  it('default scheduled entrypoint makes no network request or dispatch and creates no state', async () => {
    const network = vi.fn(async () => { throw new Error('network_forbidden'); });
    vi.stubGlobal('fetch', network);
    try {
      await worker.scheduled({ scheduledTime: instant, cron: '*/10 * * * *', noRetry() {} }, localEnv());
      expect(network).not.toHaveBeenCalled();
      expect(await count('watchdog_state')).toBe(0);
      expect(await count('ops_events')).toBe(0);
    } finally { vi.unstubAllGlobals(); }
  });

  it('flows GitHub mock -> watchdog -> episode+D1 inbox -> sink -> ack -> ledger after ack loss', async () => {
    const report = await runWatchdog(env.DB, config, { now: instant, client: disabled });
    expect(report.status).toBe('ok');
    expect(report.incidents[0].code).toBe('WORKFLOW_DISABLED');
    expect(await count('watchdog_episodes')).toBe(1);
    expect(await count('ops_events')).toBe(1);
    const sinkLedger = new Map<string, string>();
    let loseAck = true;
    const fetcher = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      const event = JSON.parse(String(init?.body));
      const previous = sinkLedger.get(event.event_id);
      if (previous !== undefined && previous !== event.message) return new Response('', { status: 409 });
      sinkLedger.set(event.event_id, event.message);
      if (loseAck) { loseAck = false; throw new Error('ack_lost_after_sink_commit'); }
      return Response.json({ accepted: true, event_id: event.event_id });
    }) as typeof fetch;
    const forward = { enabled: true, url: 'https://sink.invalid/events', token: 'synthetic-sink', fetch: fetcher };
    expect((await forwardDue(new InboxRepository(env.DB), { ...forward, now: () => instant })).forwarded).toBe(0);
    await runWatchdog(env.DB, config, { now: instant + 600_000, client: disabled });
    expect((await forwardDue(new InboxRepository(env.DB), { ...forward, now: () => instant + 600_000 })).forwarded).toBe(1);
    expect(sinkLedger.size).toBe(1);
    expect(await count('ops_events')).toBe(1);
    const status = await new InboxRepository(env.DB).status(instant + 600_000);
    expect(status).toMatchObject({ pending_forwarding: 0, forwarding_attempts: 2, forwarding_failures: 1 });
  });

  it('rolls episode back when inbox capacity fails, then recovers automatically on available capacity', async () => {
    await env.DB.prepare('UPDATE ops_inbox_limits SET max_pending=1 WHERE id=1').run();
    await new InboxRepository(env.DB).accept({ event_id: 'occupying-capacity', message: 'synthetic' }, instant);
    const failure = await runWatchdog(env.DB, config, { now: instant, client: disabled });
    expect(failure.status).toBe('state_unavailable');
    expect(await count('watchdog_episodes')).toBe(0);
    // Simulate existing event being delivered; no operator changes a quota.
    const repository = new InboxRepository(env.DB);
    const lease = await repository.claimDue(instant);
    expect(await repository.finishAttempt(lease!, { accepted: true }, instant)).toBe(true);
    expect((await runWatchdog(env.DB, config, { now: instant + 600_000, client: disabled })).status).toBe('ok');
    expect(await count('watchdog_episodes')).toBe(1);
    expect(await count('ops_events')).toBe(2);
  });

  it('rolls episode back on conflicting durable identity', async () => {
    await new InboxRepository(env.DB).accept({ event_id: 'scheduler:WORKFLOW_DISABLED:1', message: 'different' }, instant);
    expect((await runWatchdog(env.DB, config, { now: instant, client: disabled })).status).toBe('state_unavailable');
    expect(await count('watchdog_episodes')).toBe(0);
    expect(await count('ops_events')).toBe(1);
  });

  it('replays after sink accepts but local ledger update fails, preserving one sink identity', async () => {
    const repository = new InboxRepository(env.DB);
    await repository.accept({ event_id: 'ledger-boundary', message: 'synthetic' }, instant);
    const delivered = new Set<string>();
    const fetcher = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      const event = JSON.parse(String(init?.body)); delivered.add(event.event_id);
      return Response.json({ accepted: true, event_id: event.event_id });
    }) as typeof fetch;
    vi.spyOn(repository, 'finishAttempt').mockRejectedValueOnce(new Error('synthetic_storage_failure'));
    const forward = { enabled: true, url: 'https://sink.invalid/events', token: 'synthetic', fetch: fetcher };
    await expect(forwardDue(repository, { ...forward, now: () => instant })).rejects.toThrow('synthetic_storage_failure');
    expect((await new InboxRepository(env.DB).status(instant)).pending_forwarding).toBe(1);
    expect((await forwardDue(new InboxRepository(env.DB), { ...forward, now: () => instant + 31_000 })).forwarded).toBe(1);
    expect(delivered.size).toBe(1);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('preserves immutable identities and admission counters through retention', async () => {
    const repository = new InboxRepository(env.DB);
    await repository.accept({ event_id: 'retained', message: 'original' }, instant);
    const lease = await repository.claimDue(instant);
    await repository.finishAttempt(lease!, { accepted: true }, instant);
    expect(await repository.retainForwarded(instant + 1)).toBe(1);
    expect(await repository.accept({ event_id: 'retained', message: 'original' })).toMatchObject({ duplicate: true });
    await expect(env.DB.prepare("DELETE FROM ops_events WHERE event_id='retained'").run()).rejects.toThrow();
    expect(await repository.status()).toMatchObject({ persisted_events: 1, dedup_tombstones: 1, pending_forwarding: 0 });
  });
});
