import { handleInboxRequest, withDeadline } from './inbox';
import { InboxRepository } from './inbox_repository';
import { forwardDue } from './forwarding';
import { runWatchdog, watchdogHealth, type WatchdogConfig } from './watchdog';

export interface Env {
  DB: D1Database;
  WATCHDOG_ENABLED?: string;
  DELIVERY_ENABLED?: string;
  RECOVERY_ENABLED?: string;
  FORWARDING_ENABLED?: string;
  GITHUB_REPOSITORY: string;
  GITHUB_WORKFLOW: string;
  GITHUB_APP_ID?: string;
  GITHUB_INSTALLATION_ID?: string;
  GITHUB_APP_PRIVATE_KEY?: string;
  INBOX_TOKEN?: string;
  HEALTH_TOKEN?: string;
  FORWARD_URL?: string;
  FORWARD_TOKEN?: string;
}

export function watchdogConfig(env: Env): WatchdogConfig {
  return {
    watchdogEnabled: env.WATCHDOG_ENABLED === 'true',
    deliveryEnabled: env.DELIVERY_ENABLED === 'true',
    recoveryEnabled: env.RECOVERY_ENABLED === 'true',
    repository: env.GITHUB_REPOSITORY,
    workflow: env.GITHUB_WORKFLOW,
    credentials: {
      appId: env.GITHUB_APP_ID ?? '',
      installationId: env.GITHUB_INSTALLATION_ID ?? '',
      privateKeyPem: env.GITHUB_APP_PRIVATE_KEY ?? '',
    },
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const repository = new InboxRepository(env.DB);
    const health = request.method === 'GET' && new URL(request.url).pathname === '/health';
    const response = await handleInboxRequest(request, {
      repository,
      token: health ? (env.HEALTH_TOKEN ?? '') : (env.INBOX_TOKEN ?? ''),
    });
    if (!health || response.status !== 200) return response;
    try {
      const inbox = await response.json() as Record<string, unknown>;
      const watchdog = await withDeadline(watchdogHealth(env.DB), 5000, 'storage_unavailable');
      const enabled = env.WATCHDOG_ENABLED === 'true' && env.DELIVERY_ENABLED === 'true';
      const healthy = enabled && !watchdog.heartbeat_stale &&
        Number(inbox.quarantined_events) === 0 && Number(inbox.oldest_pending_age) < 3_600_000 &&
        Number(inbox.pending_forwarding) < Number(inbox.max_pending) &&
        Number(inbox.persisted_events) < Number(inbox.max_events) &&
        Number(inbox.retained_payload_bytes) < Number(inbox.max_payload_bytes) &&
        watchdog.last_successful_observation !== null &&
        Date.now() - Number(watchdog.last_successful_observation) < 1_800_000;
      return Response.json({ healthy, inbox, watchdog, production_gates_open: enabled }, {
        status: healthy ? 200 : 503, headers: { 'Cache-Control': 'no-store' },
      });
    } catch {
      return Response.json({ healthy: false, error: 'storage_unavailable' }, {
        status: 503, headers: { 'Cache-Control': 'no-store' },
      });
    }
  },

  async scheduled(controller: ScheduledController, env: Env): Promise<void> {
    const result = await runWatchdog(env.DB, watchdogConfig(env), {
      scheduledTime: controller.scheduledTime,
    });
    // No production endpoint/credential is supplied in local configuration.
    // Inbox retries remain independent of a failed GitHub observation.
    await forwardDue(new InboxRepository(env.DB), {
      enabled: env.FORWARDING_ENABLED === 'true',
      url: env.FORWARD_URL ?? '', token: env.FORWARD_TOKEN ?? '',
    });
    if (result.status === 'state_unavailable') throw new Error('ops_state_unavailable');
  },
} satisfies ExportedHandler<Env>;
