import { GitHubAppAuth, GitHubError, githubRequest, type AppCredentials, type GitHubFetch } from "./github_auth";

export interface WorkflowRun {
  id: number; head_branch: string; event: string; display_title: string;
  created_at: string; run_started_at?: string | null; updated_at?: string;
  status: string; conclusion?: string | null;
}
export interface Inspection { state: string; runs: WorkflowRun[] }
export interface ActionsClient { inspect(now: number): Promise<Inspection>; dispatch(beforeSend?: () => Promise<void>): Promise<void> }

export class GitHubActionsClient implements ActionsClient {
  private readonly base: string;
  private readonly auth: GitHubAppAuth;
  constructor(repository: string, workflow: string, credentials: AppCredentials,
    private readonly recoveryEnabled = false, private readonly fetcher: GitHubFetch = fetch,
    private readonly clock: () => number = Date.now) {
    if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository) || !/^[A-Za-z0-9_.-]+\.ya?ml$/.test(workflow))
      throw new GitHubError("repository_workflow_invalid");
    this.base = `https://api.github.com/repos/${repository}/actions/workflows/${workflow}`;
    this.auth = new GitHubAppAuth(credentials, repository, recoveryEnabled ? "write" : "read", fetcher, clock);
  }
  private async request(url: string, payload?: unknown, beforeSend?: () => Promise<void>): Promise<unknown> {
    for (let attempt = 0; attempt < 2; attempt++) {
      const token = await this.auth.getToken();
      await beforeSend?.();
      try { return await githubRequest(this.fetcher, url, token, this.clock(), payload); }
      catch (error) {
        // Only GET may retry. An ambiguous POST always consumes its reservation.
        if (!(error instanceof GitHubError) || error.status !== 401 || payload !== undefined || attempt !== 0) throw error;
        this.auth.invalidate();
      }
    }
    throw new GitHubError("github_authentication_unavailable");
  }
  async inspect(now: number): Promise<Inspection> {
    const metadata = await this.request(this.base) as { state?: unknown };
    if (typeof metadata?.state !== "string") throw new GitHubError("workflow_metadata_invalid");
    if (metadata.state !== "active") return { state: metadata.state, runs: [] };
    const runs: WorkflowRun[] = [];
    const created = `${new Date(now - 172_800_000).toISOString()}..${new Date(now).toISOString()}`;
    for (let page = 1; page <= 5; page++) {
      const query = new URLSearchParams({ branch: "main", created, per_page: "100", page: String(page) });
      const result = await this.request(`${this.base}/runs?${query}`) as { workflow_runs?: unknown; total_count?: unknown };
      if (!Array.isArray(result?.workflow_runs) || result.workflow_runs.length > 100 ||
        !Number.isSafeInteger(result.total_count) || (result.total_count as number) < 0) throw new GitHubError("run_metadata_invalid");
      if ((result.total_count as number) > 500) throw new GitHubError("run_metadata_truncated");
      for (const run of result.workflow_runs) {
        if (!run || !Number.isSafeInteger(run.id) || typeof run.head_branch !== "string" ||
          typeof run.event !== "string" || typeof run.display_title !== "string" ||
          typeof run.status !== "string" || !Number.isFinite(Date.parse(run.created_at)) ||
          (run.run_started_at && !Number.isFinite(Date.parse(run.run_started_at))) ||
          (run.updated_at && !Number.isFinite(Date.parse(run.updated_at)))) throw new GitHubError("run_metadata_invalid");
        runs.push(run as WorkflowRun);
      }
      if (runs.length >= (result.total_count as number)) return { state: metadata.state, runs };
      if (result.workflow_runs.length < 100) throw new GitHubError("run_metadata_incomplete");
    }
    throw new GitHubError("run_metadata_truncated");
  }
  async dispatch(beforeSend?: () => Promise<void>): Promise<void> {
    if (!this.recoveryEnabled) throw new GitHubError("recovery_permission_required");
    await this.request(`${this.base}/dispatches`, { ref: "main", inputs: { mode: "collect-and-deliver" } }, beforeSend);
  }
}
