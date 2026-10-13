# Ops27: Workers/D1 watchdog and GitHub App prototype

Scope: issue [#33](https://github.com/hmono/Luka-Tennis-Player/issues/33), read-only
review of [PR #32](https://github.com/hmono/Luka-Tennis-Player/pull/32), and Ops26
implementation/review in `/home/ono/ops26/integration`. This proposal begins on
main `944e417`; it does not provision or activate anything.

## Behavior and contracts

`runWatchdog(db: D1Database, config, options)` requires literal boolean
`watchdogEnabled` and `deliveryEnabled` before token grants, state mutations,
dispatches or queue insertions. Recovery additionally requires literal boolean
`recoveryEnabled`. Defaults and production handler gating belong to coordinator.
`watchdogHealth(db, now)` exposes last completed cycle, last start, last successful
GitHub observation, durable API cooldown, heartbeat age/staleness, active episodes
and reservation count. An independent service outside GitHub AND Cloudflare must
consume these signals; the Worker cannot alert about its own total absence.

Daily UTC slots are 12:17 and 18:17, plus Monday 12:00; latest due slot has a
90-minute grace. Observation requires `main`, `schedule`, or `workflow_dispatch`
with the exact existing run-name contract `ATP rankings collect-and-deliver`.
Substring matches and development/dry-run/manual runs are excluded. Production
schedule classification additionally depends on the coherent local delivery gate;
the GitHub repository delivery variable must be independently verified as part
of activation. The minimal Actions-only App cannot read repository variables to
prove that coherence. A successful run proves execution, not source freshness or
device delivery. A following slot cannot conceal the previous missing one.

Persisted incident codes are `MISSED_RUN`, `RUN_FAILURE`, `SCHEDULER_DELAY`,
`RUN_DURATION`, `WORKFLOW_DISABLED` and `MONITOR_UNAVAILABLE`. Code scopes are
fixed (six run/monitor scopes plus one cron-delay scope); episode generation
increases only after an observed recovery. Unknown API observations preserve
previous failure/disabled episodes rather than inventing recovery. Continuous
failure produces one ID across slots, restarts and lost acknowledgments. A new
failure after recovery gets a new ID. The incident and its inbox insertion share
one D1 batch: quota rejection/conflicting payload aborts both. Recovery events
use that same transaction boundary. The inbox's retained IDs provide retry
deduplication; its acceptance still means queue acceptance only.

Cron lag over two minutes, or a completed-cycle gap over twenty minutes, opens a
separate scheduler-delay episode on the next invocation. Health identifies the
absence while no invocation arrives. This does not reconstruct a complete history
of every missed ranking slot: assessment intentionally covers the latest due slot.

## Recovery, concurrency and storage

An atomic D1 compare-and-set lease serializes observation; SQL fencing on episode,
outbox, health and reservation mutations blocks a superseded isolate. Durable
`INSERT ... SELECT ... HAVING ... RETURNING` is the dispatch-budget authority:
at most two reservations per slot, at least thirty minutes apart, within six
hours of the slot. The reservation commits before POST; crashes/timeouts consume
the budget. No workflow-enable endpoint exists. Disabled workflow, unavailable
metadata, timing-only incidents and false release gates never dispatch.

GET403/429 cooldowns persist; default outage cooldown is ten minutes, and server
Retry-After/primary reset can extend it. Repeated checks during cooldown make no
GitHub calls. Concurrent lease losers make no GitHub calls. A monotonic completed
cycle watermark rejects old cron replays. Dispatch reservations older than one
day are removed only after the watermark check; their six-hour recovery horizon
has closed. Fixed-scope episode generations and overwritten health rows remain.
Inbox pending work and dedup IDs are never pruned here. Clock rollback fails
closed until wall clock passes the previous watermark; disaster restore of an old
database remains an external risk requiring a qualified restore protocol.

## App and HTTP security

JWT signing uses WebCrypto `RSASSA-PKCS1-v1_5` / SHA-256, keys at least 2048 bits,
and both PKCS8 and GitHub PKCS1 PEM (explicit rsaEncryption PKCS8 wrapper).
JWT iat is now minus sixty seconds and exp now plus 540 seconds. Installation
grant requests exactly one configured repository and Actions read; write is
requested only for recovery-enabled clients. Installation/App permissions must
also be restricted externally; token downscoping does not repair an overpowered
installation. No Contents, Issues or Administration permission is requested.

Tokens/JWT/private key stay in isolate memory, never D1/logs/files. Token cache
is replaced only after validating a nonempty token and expiry more than sixty
seconds away. It renews at the safety margin and shares concurrent renewal within
an auth instance. GET401 renews once; dispatch POST401 is never replayed.

Every HTTP operation has a fifteen-second total deadline covering headers and
streamed body, an AbortController and Promise.race for even an uncooperative
synthetic fetch. Redirects fail, response bodies are capped at 2MB and errors
expose only sanitized code/status/retry deadline. Recent-run filtering covers two
days with at most five pages/500 runs; exactly500 complete runs are accepted,
501 fails closed. Ordinary inspection costs at most seven HTTP operations
(grant, workflow, five run pages). A read401 can add one renewal and one replay
per GET; each POST is single-attempt. Default ten-minute cycles, these caps, D1
quota admission and bounded outbox processing constrain request storms. CPU time,
actual quotas/cost and real token/endpoint qualification remain outside mock proof.

Official references reviewed:
[D1 transactions](https://developers.cloudflare.com/d1/worker-api/d1-database/),
[Actions run filtering](https://docs.github.com/en/rest/actions/workflow-runs),
[installation-token downscoping](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).

## Synthetic validation and limits

`workers/atp-ops/test/watchdog.test.ts` targets the coordinator's current official
Workers Vitest integration (`cloudflare:workers` env, migrated local D1 per test
in remote CI). Cases cover eight-week slots and renewable credentials; persistent
failure/disabled episodes and distinct recoveries; missing/delayed cron;
development/dry-run filtering; exact500/overflow metadata; invalid/expiring App
tokens, actual synthetic RSA signature/PKCS1 conversion; 401/403/429; full header
and body deadlines; body limits; concurrent schedules/reservations; superseded
leases; crash after reservation; repeated pending alerts; quota/conflict atomic
rollback; stale replay and health.

No dependency installation, local test suite, production key reads, App grant,
dispatch, workflow enable, Cloudflare deploy/resource creation or operational
message was performed. Remote integrated CI and independent review belong to the
coordinator; this report does not claim tests passed before that evidence exists.
`STAGING_NO_GO` and `ACTIVATION_NO_GO` remain. Missing real account entitlements,
supervision, production flag coherence, sink delivery, backup/restore, CPU/cost and
secret provisioning cannot be established by this prototype.
