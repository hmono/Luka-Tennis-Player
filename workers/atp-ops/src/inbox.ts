import { InboxError, InboxRepository, type InboxEvent } from './inbox_repository';

export interface InboxRequestOptions {
  repository: InboxRepository; token: string; bodyDeadlineMs?: number; requestDeadlineMs?: number;
}
export function withDeadline<T>(work: Promise<T>, ms: number, code = 'timeout', cancel?: () => void): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => { cancel?.(); reject(new InboxError(code)); }, ms);
  });
  return Promise.race([work, timeout]).finally(() => clearTimeout(timer));
}
/** Bounds complete body time, including a peer that continuously drips bytes. */
export async function readBoundedBody(body: ReadableStream<Uint8Array> | null, maxBytes: number,
  deadlineMs: number, signal?: AbortSignal): Promise<string> {
  if (!body) return '';
  const reader = body.getReader();
  const cancel = () => { void reader.cancel().catch(() => undefined); };
  signal?.addEventListener('abort', cancel, { once: true });
  try {
    const work = (async () => {
      const chunks: Uint8Array[] = [];
      let size = 0;
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.byteLength;
        if (size > maxBytes) { cancel(); throw new InboxError('response_too_large'); }
        chunks.push(part.value);
      }
      const bytes = new Uint8Array(size);
      let offset = 0;
      for (const part of chunks) { bytes.set(part, offset); offset += part.byteLength; }
      try { return new TextDecoder('utf-8', { fatal: true, ignoreBOM: false }).decode(bytes); }
      catch { throw new InboxError('invalid_event'); }
    })();
    return await withDeadline(work, deadlineMs, 'timeout', cancel);
  } finally { signal?.removeEventListener('abort', cancel); }
}

function respond(status: number, value: unknown): Response {
  return Response.json(value, { status, headers: {
    'Cache-Control': 'no-store', ...(status === 503 ? { 'Retry-After': '1' } : {}),
  } });
}
async function authorized(request: Request, token: string): Promise<boolean> {
  if (!token || token.length > 4096) return false;
  const value = request.headers.get('authorization') ?? '';
  if (value.length > 4103) return false;
  const encoder = new TextEncoder();
  const [actual, expected] = await Promise.all([
    crypto.subtle.digest('SHA-256', encoder.encode(value)),
    crypto.subtle.digest('SHA-256', encoder.encode(`Bearer ${token}`)),
  ]);
  const a = new Uint8Array(actual), b = new Uint8Array(expected);
  let difference = 0;
  for (let i = 0; i < a.length; i++) difference |= a[i] ^ b[i];
  return difference === 0;
}
export async function handleInboxRequest(request: Request, options: InboxRequestOptions): Promise<Response> {
  if (!await authorized(request, options.token)) return respond(401, { error: 'unauthorized' });
  const path = new URL(request.url).pathname;
  if (request.method === 'GET' && path === '/health') {
    try {
      return respond(200, await withDeadline(options.repository.status(), options.requestDeadlineMs ?? 5000,
        'storage_unavailable'));
    } catch { return respond(503, { error: 'storage_unavailable' }); }
  }
  if (request.method !== 'POST' || path !== '/events') return respond(404, { error: 'not_found' });
  if (!/^application\/json(?:\s*;[^\r\n]*)?$/i.test(request.headers.get('content-type') ?? '')) {
    return respond(415, { error: 'json_required' });
  }
  const length = request.headers.get('content-length');
  if (length !== null && (!/^[0-9]+$/.test(length) || Number(length) < 1 || Number(length) > 8192)) {
    return respond(400, { error: 'invalid_size' });
  }
  try {
    const text = await readBoundedBody(request.body, 8192, options.bodyDeadlineMs ?? 5000);
    if (length !== null && new TextEncoder().encode(text).byteLength !== Number(length)) {
      throw new InboxError('invalid_size');
    }
    const event = JSON.parse(text) as unknown;
    if (!event || typeof event !== 'object' || Array.isArray(event) ||
      Object.keys(event).some((key) => !['event_id', 'message', 'kind'].includes(key))) {
      throw new InboxError('invalid_event');
    }
    let ack;
    try {
      ack = await withDeadline(options.repository.accept(event as InboxEvent),
        options.requestDeadlineMs ?? 5000, 'storage_unavailable');
    } catch (error) {
      if (!(error instanceof InboxError)) throw new InboxError('storage_unavailable');
      throw error;
    }
    return respond(200, ack);
  } catch (error) {
    const code = error instanceof InboxError ? error.code : 'invalid_event';
    if (code === 'timeout') return respond(408, { error: 'request_timeout' });
    if (code === 'event_id_conflict') return respond(409, { error: code });
    if (code === 'storage_unavailable' || code === 'inbox_capacity') return respond(503, { error: code });
    return respond(400, { error: code === 'response_too_large' ? 'invalid_size' : code });
  }
}
