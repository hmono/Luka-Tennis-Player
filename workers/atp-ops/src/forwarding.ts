import { InboxError, InboxRepository, type AttemptOutcome, type InboxLease } from './inbox_repository';
import { readBoundedBody, withDeadline } from './inbox';

export interface ForwardingOptions {
  /** Production entrypoint must keep this false until separately qualified. */
  enabled: boolean; url: string; token: string;
  fetch?: typeof fetch; timeoutMs?: number; maxResponseBytes?: number; maxBatch?: number;
  now?: () => number;
}
export function validForwardDestination(value: string): boolean {
  if (!value || /[\s\u0000-\u001f\u007f]/u.test(value)) return false;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !!url.hostname && !url.username && !url.password && !url.hash;
  } catch { return false; }
}
function retryAfterMs(response: Response): number | undefined {
  const value = response.headers.get('retry-after');
  // Do not trust provider timestamps or arbitrarily large retry delays.
  return value && /^[0-9]+$/.test(value) ? Math.min(3_600_000, Number(value) * 1000) : undefined;
}
export async function sendToDurableSink(lease: InboxLease, options: ForwardingOptions): Promise<AttemptOutcome> {
  if (!validForwardDestination(options.url) || !options.token || /[\r\n]/.test(options.token)) {
    return { accepted: false, errorCode: 'invalid_forward_config' };
  }
  const timeoutMs = options.timeoutMs ?? 10_000;
  const abort = new AbortController();
  const work = (async (): Promise<AttemptOutcome> => {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(lease.event_id));
    const key = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
    const response = await (options.fetch ?? fetch)(options.url, {
      method: 'POST', redirect: 'manual', signal: abort.signal,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${options.token}`, 'Idempotency-Key': key },
      body: JSON.stringify({ event_id: lease.event_id, message: lease.message }),
    });
    if (response.status < 200 || response.status >= 300) {
      void response.body?.cancel().catch(() => undefined);
      return { accepted: false, errorCode: `http_${response.status}`, retryAfterMs: retryAfterMs(response) };
    }
    const body = await readBoundedBody(response.body, options.maxResponseBytes ?? 8192, timeoutMs, abort.signal);
    let ack: unknown;
    try { ack = JSON.parse(body); } catch { return { accepted: false, errorCode: 'invalid_ack' }; }
    return ack && typeof ack === 'object' && !Array.isArray(ack) &&
      (ack as Record<string, unknown>).accepted === true &&
      (ack as Record<string, unknown>).event_id === lease.event_id
      ? { accepted: true } : { accepted: false, errorCode: 'invalid_ack' };
  })();
  try { return await withDeadline(work, timeoutMs, 'timeout', () => abort.abort()); }
  catch (error) {
    return { accepted: false, errorCode: error instanceof InboxError &&
      ['timeout', 'response_too_large'].includes(error.code) ? error.code : 'transport_error' };
  } finally { abort.abort(); }
}
export async function forwardDue(repository: InboxRepository, options: ForwardingOptions) {
  const summary = { attempted: 0, forwarded: 0, failures: 0, disabled: !options.enabled };
  if (!options.enabled) return summary;
  const timeout = options.timeoutMs ?? 10_000;
  const batch = options.maxBatch ?? 4;
  const maxResponseBytes = options.maxResponseBytes ?? 8192;
  if (!Number.isSafeInteger(timeout) || timeout < 1 || timeout > 15_000 || repository.leaseMs < timeout + 1000 ||
      !Number.isSafeInteger(batch) || batch < 1 || batch > 16 || !Number.isSafeInteger(maxResponseBytes) ||
      maxResponseBytes < 1 || maxResponseBytes > 8192 || !validForwardDestination(options.url) ||
      !options.token || options.token.length > 4096 || /[\r\n]/.test(options.token)) {
    throw new InboxError('invalid_forward_config');
  }
  const now = options.now ?? Date.now;
  for (let index = 0; index < batch; index++) {
    const lease = await repository.claimDue(now());
    if (!lease) break;
    summary.attempted++;
    const outcome = await sendToDurableSink(lease, options);
    // A failed commit leaves the durable lease for expiry/replay. Propagate the
    // storage error; don't invent success or release somebody else's lease.
    const committed = await repository.finishAttempt(lease, outcome, now());
    if (committed && outcome.accepted) summary.forwarded++;
    else summary.failures++;
  }
  return summary;
}
