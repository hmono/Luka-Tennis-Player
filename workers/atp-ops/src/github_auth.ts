/** GitHub App signing and installation credentials stay in isolate memory only. */
export interface AppCredentials { appId: string; installationId: string; privateKeyPem: string }
export type GitHubFetch = typeof fetch;

export class GitHubError extends Error {
  constructor(public readonly code: string, public readonly status = 0, public readonly retryAt = 0) {
    super(code);
  }
}

const encoder = new TextEncoder();
const b64url = (bytes: Uint8Array): string => btoa(String.fromCharCode(...bytes)).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
const encode = (value: unknown): string => b64url(encoder.encode(JSON.stringify(value)));

function der(tag: number, body: Uint8Array): Uint8Array {
  let length = body.length;
  const lengthBytes: number[] = [];
  while (length) { lengthBytes.unshift(length & 255); length >>>= 8; }
  return new Uint8Array([tag, ...(body.length < 128 ? [body.length] : [128 | lengthBytes.length, ...lengthBytes]), ...body]);
}

function privateKeyDer(pem: string): Uint8Array {
  const match = /^\s*-----BEGIN (RSA PRIVATE KEY|PRIVATE KEY)-----\s*([A-Za-z0-9+/=\s]+)-----END \1-----\s*$/.exec(pem);
  if (!match || pem.length > 16_384) throw new GitHubError("app_key_invalid");
  let bytes: Uint8Array;
  try { bytes = Uint8Array.from(atob(match[2].replace(/\s/g, "")), c => c.charCodeAt(0)); }
  catch { throw new GitHubError("app_key_invalid"); }
  if (match[1] === "RSA PRIVATE KEY") {
    // PKCS#1 keys issued by GitHub need the PKCS#8 rsaEncryption wrapper.
    const algorithm = [0x30, 0x0d, 0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01, 0x05, 0x00];
    bytes = der(0x30, new Uint8Array([0x02, 0x01, 0x00, ...algorithm, ...der(0x04, bytes)]));
  }
  return bytes;
}

export async function signAppJwt(credentials: AppCredentials, now: number): Promise<string> {
  if (!/^\d+$/.test(credentials.appId) || !/^\d+$/.test(credentials.installationId)) throw new GitHubError("app_identity_invalid");
  try {
    const key = await crypto.subtle.importKey("pkcs8", privateKeyDer(credentials.privateKeyPem),
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
    if ((key.algorithm as RsaKeyAlgorithm).modulusLength < 2048) throw new GitHubError("app_key_invalid");
    const instant = Math.floor(now / 1000);
    const input = `${encode({ alg: "RS256", typ: "JWT" })}.${encode({ iat: instant - 60, exp: instant + 540, iss: credentials.appId })}`;
    const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, encoder.encode(input));
    return `${input}.${b64url(new Uint8Array(signature))}`;
  } catch { throw new GitHubError("app_signing_unavailable"); }
}

/** A total deadline covers headers AND streamed body; redirects are rejected. */
export async function githubRequest(fetcher: GitHubFetch, url: string, token: string, now: number,
  payload?: unknown, deadlineMs = 15_000): Promise<unknown> {
  const abort = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => { abort.abort(); reject(new GitHubError("github_deadline")); }, deadlineMs);
  });
  const exchange = async (): Promise<unknown> => {
    const response = await fetcher(url, {
      method: payload === undefined ? "GET" : "POST", redirect: "error", signal: abort.signal,
      headers: { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        Authorization: `Bearer ${token}`, "User-Agent": "atp-ops27-watchdog", "Content-Type": "application/json" },
      ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
    });
    if (abort.signal.aborted) { await response.body?.cancel(); throw new GitHubError("github_deadline"); }
    if (!response.ok) {
      let retryAt = 0;
      if (response.status === 403 || response.status === 429) {
        const after = response.headers.get("retry-after") ?? "";
        const seconds = /^\d+$/.test(after) ? Number(after) * 1000 : Date.parse(after) - now;
        const reset = response.headers.get("x-ratelimit-remaining") === "0"
          ? Number(response.headers.get("x-ratelimit-reset")) * 1000 - now : 0;
        retryAt = now + Math.max(600_000, Number.isFinite(seconds) ? seconds : 0, Number.isFinite(reset) ? reset : 0);
      }
      await response.body?.cancel();
      throw new GitHubError("github_http", response.status, retryAt);
    }
    if (response.status === 204) { await response.body?.cancel(); return null; }
    if (!response.body) throw new GitHubError("github_body_invalid");
    const reader = response.body.getReader();
    // Cancel the stream too: a mocked/adapter fetch may ignore its signal.
    const cancelReader = (): void => { void reader.cancel().catch(() => undefined); };
    abort.signal.addEventListener("abort", cancelReader, { once: true });
    const chunks: Uint8Array[] = [];
    let size = 0;
    try {
      while (true) {
        const result = await reader.read();
        if (result.done) break;
        size += result.value.length;
        if (size > 2_000_000) throw new GitHubError("github_body_limit");
        chunks.push(result.value);
      }
    } finally { abort.signal.removeEventListener("abort", cancelReader); await reader.cancel().catch(() => undefined); }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    try { return JSON.parse(new TextDecoder().decode(bytes)); }
    catch { throw new GitHubError("github_body_invalid"); }
  };
  try { return await Promise.race([exchange(), deadline]); }
  catch (error) { if (error instanceof GitHubError) throw error; throw new GitHubError("github_transport"); }
  finally { if (timer !== undefined) clearTimeout(timer); abort.abort(); }
}

export class GitHubAppAuth {
  private token = "";
  private expires = 0;
  private pending: Promise<string> | undefined;
  constructor(private readonly credentials: AppCredentials, private readonly repository: string,
    private readonly actions: "read" | "write", private readonly fetcher: GitHubFetch = fetch,
    private readonly clock: () => number = Date.now) {}

  invalidate(): void { this.token = ""; this.expires = 0; }
  async getToken(): Promise<string> {
    if (this.token && this.expires > this.clock() + 60_000) return this.token;
    if (this.pending) return this.pending;
    this.pending = this.mint();
    try { return await this.pending; } finally { this.pending = undefined; }
  }
  private async mint(): Promise<string> {
    const now = this.clock();
    if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(this.repository)) throw new GitHubError("repository_invalid");
    const jwt = await signAppJwt(this.credentials, now);
    const grant = await githubRequest(this.fetcher,
      `https://api.github.com/app/installations/${this.credentials.installationId}/access_tokens`, jwt, now,
      { repositories: [this.repository.split("/")[1]], permissions: { actions: this.actions } }) as { token?: unknown; expires_at?: unknown };
    const expires = typeof grant?.expires_at === "string" ? Date.parse(grant.expires_at) : NaN;
    if (typeof grant?.token !== "string" || !grant.token || !Number.isFinite(expires) || expires <= this.clock() + 60_000)
      throw new GitHubError("installation_token_invalid");
    this.token = grant.token; this.expires = expires;
    return this.token;
  }
}
