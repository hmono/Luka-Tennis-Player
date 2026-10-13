import { env } from 'cloudflare:workers';
import { describe, expect, it, vi } from 'vitest';
import { type ActionsClient, type WorkflowRun } from '../src/github_client';
import { GitHubError } from '../src/github_auth';
import { runWatchdog, type WatchdogConfig } from '../src/watchdog';

// Independent reviewer fixtures. No real App key, network, dispatch or resource.
const instant = Date.parse('2026-10-13T14:00:00Z');
const slot = '2026-10-13T12:17:00.000Z';
const config: WatchdogConfig = {
  watchdogEnabled: true, deliveryEnabled: true, recoveryEnabled: false,
  repository: 'synthetic/repository', workflow: 'update_rankings.yml',
  credentials: { appId: '1', installationId: '2', privateKeyPem: 'synthetic-unused' },
};
const run = (override: Partial<WorkflowRun> = {}): WorkflowRun => ({
  id: 1, head_branch: 'main', event: 'schedule',
  display_title: 'ATP rankings collect-and-deliver', created_at: slot,
  run_started_at: slot, updated_at: '2026-10-13T12:18:00Z',
  status: 'completed', conclusion: 'failure', ...override,
});
const client = (runs: WorkflowRun[] = []): ActionsClient => ({
  inspect: vi.fn(async () => ({ state: 'active', runs })),
  dispatch: vi.fn(async () => {}),
});
const identities = async () => (await env.DB.prepare('SELECT event_id FROM ops_events ORDER BY event_id')
  .all<{ event_id: string }>()).results.map(row => row.event_id);
const failureEpisode = () => env.DB.prepare(
  "SELECT active,generation FROM watchdog_episodes WHERE scope='RUN_FAILURE'",
).first<{ active: number; generation: number }>();

describe('independent Ops27 adversarial regression gates', () => {
  it.each(['queued', 'in_progress'])('IR-01 preserves a failure while a newer retry is %s', async status => {
    await runWatchdog(env.DB, config, { now: instant, client: client([run()]) });
    const retry = run({ id: 2, event: 'workflow_dispatch',
      created_at: '2026-10-13T14:01:00Z', run_started_at: '2026-10-13T14:01:00Z',
      updated_at: '2026-10-13T14:01:00Z', status, conclusion: null });
    const pendingClient = client([run(), retry]);
    await runWatchdog(env.DB, { ...config, recoveryEnabled: true }, {
      now: instant + 600_000, client: pendingClient,
    });
    expect(pendingClient.dispatch).not.toHaveBeenCalled();
    expect(await failureEpisode()).toEqual({ active: 1, generation: 1 });
    expect(await identities()).not.toContain('scheduler:RECOVERED:RUN_FAILURE:1');

    // Another failed attempt belongs to the same failure episode.
    const retryFailure = { ...retry, status: 'completed', conclusion: 'failure',
      updated_at: '2026-10-13T14:12:00Z' };
    await runWatchdog(env.DB, config, { now: instant + 1_200_000, client: client([run(), retryFailure]) });
    expect(await failureEpisode()).toEqual({ active: 1, generation: 1 });
    expect((await identities()).filter(id => id.startsWith('scheduler:RUN_FAILURE:')))
      .toEqual(['scheduler:RUN_FAILURE:1']);

    // A completed successful replacement provides the positive recovery evidence.
    const success = { ...retryFailure, id: 3, created_at: '2026-10-13T14:13:00Z',
      run_started_at: '2026-10-13T14:13:00Z', updated_at: '2026-10-13T14:14:00Z', conclusion: 'success' };
    await runWatchdog(env.DB, config, { now: instant + 1_800_000, client: client([run(), retryFailure, success]) });
    expect(await failureEpisode()).toEqual({ active: 0, generation: 1 });
    expect((await identities()).filter(id => id.startsWith('scheduler:RECOVERED:RUN_FAILURE:')))
      .toEqual(['scheduler:RECOVERED:RUN_FAILURE:1']);
  });

  it('IR-02 fences dispatch and its completion when ownership changes after reservation', async () => {
    const api = client();
    const replacement = JSON.stringify({ id: 'synthetic-replacement', expires: instant + 1_200_000 });
    await runWatchdog(env.DB, { ...config, recoveryEnabled: true }, {
      now: instant, client: api,
      afterReservation: async () => {
        await env.DB.prepare("UPDATE watchdog_state SET value=? WHERE key='cycle_lease'")
          .bind(replacement).run();
      },
    });
    expect(api.dispatch).not.toHaveBeenCalled();
    expect(await env.DB.prepare('SELECT attempt,result FROM watchdog_dispatches').first())
      .toEqual({ attempt: 1, result: 'reserved' });
    expect(await env.DB.prepare("SELECT value FROM watchdog_state WHERE key='cycle_lease'").first('value'))
      .toBe(replacement);
  });

  it('IR-02 cannot reserve or dispatch after its own lease expires without a takeover', async () => {
    let clock = instant;
    const mockedClock = vi.spyOn(Date, 'now').mockImplementation(() => clock);
    const api = client();
    api.inspect = vi.fn(async () => {
      clock += 600_000;
      return { state: 'active', runs: [] };
    });
    try {
      // Omit options.now: exercise the production wall clock behavior.
      await runWatchdog(env.DB, { ...config, recoveryEnabled: true }, { client: api });
      expect(api.dispatch).not.toHaveBeenCalled();
      expect(await env.DB.prepare('SELECT COUNT(*) AS n FROM watchdog_dispatches').first('n')).toBe(0);
    } finally { mockedClock.mockRestore(); }
  });

  it('IR-02 measures the thirty-minute reservation cooldown at commit time', async () => {
    let clock = instant;
    const mockedClock = vi.spyOn(Date, 'now').mockImplementation(() => clock);
    const postedAt: number[] = [];
    let inspections = 0;
    const api: ActionsClient = {
      inspect: vi.fn(async () => {
        if (++inspections === 1) clock += 240_000; // Slow inspection, still inside the five-minute lease.
        return { state: 'active', runs: [] };
      }),
      dispatch: vi.fn(async () => { postedAt.push(clock); }),
    };
    try {
      await runWatchdog(env.DB, { ...config, recoveryEnabled: true }, { client: api });
      expect(postedAt).toEqual([instant + 240_000]);
      clock = instant + 1_800_000;
      await runWatchdog(env.DB, { ...config, recoveryEnabled: true }, { client: api });
      expect(postedAt).toEqual([instant + 240_000]);
      clock = instant + 2_040_000;
      await runWatchdog(env.DB, { ...config, recoveryEnabled: true }, { client: api });
      expect(postedAt).toEqual([instant + 240_000, instant + 2_040_000]);
    } finally { mockedClock.mockRestore(); }
  });

  it('recovery identity and episode close roll back together on full permanent capacity', async () => {
    await runWatchdog(env.DB, config, { now: instant, client: client([run()]) });
    await env.DB.prepare('UPDATE ops_inbox_limits SET max_events=1 WHERE id=1').run();
    const report = await runWatchdog(env.DB, config, {
      now: instant + 600_000, client: client([run({ conclusion: 'success' })]),
    });
    expect(report.status).toBe('state_unavailable');
    expect(await failureEpisode()).toEqual({ active: 1, generation: 1 });
    expect(await identities()).toEqual(['scheduler:RUN_FAILURE:1']);
  });

  it('a total GitHub outage preserves failure identity, suppresses dispatch and persists cooldown', async () => {
    await runWatchdog(env.DB, config, { now: instant, client: client([run()]) });
    const unavailable: ActionsClient = {
      inspect: vi.fn(async () => { throw new GitHubError('github_transport'); }),
      dispatch: vi.fn(async () => {}),
    };
    const enabled = { ...config, recoveryEnabled: true };
    await runWatchdog(env.DB, enabled, { now: instant + 600_000, client: unavailable });
    await runWatchdog(env.DB, enabled, { now: instant + 601_000, client: unavailable });
    expect(unavailable.inspect).toHaveBeenCalledTimes(1);
    expect(unavailable.dispatch).not.toHaveBeenCalled();
    expect(await failureEpisode()).toEqual({ active: 1, generation: 1 });
    expect(await identities()).toEqual(['scheduler:MONITOR_UNAVAILABLE:1', 'scheduler:RUN_FAILURE:1']);
  });
});
