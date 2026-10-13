# OPS-02 (#28): independent watchdog and GitHub App audit

2026-10-13 UTC. Base `944e417`; implementation branch `ops26/watchdog-auth`.
Scope: scheduler authentication, recovery budget, local durability, credentials,
and deployment contract. **Code/test proposal complete; operational activation
remains NO-GO pending external provisioning and coordinator host review.**

Only this report, `tests/ranking_alerts/test_autonomous_scheduler.py`, and the
proposal files in `docs/evidence/ops26-watchdog-patches/` were edited. Shared
production code and systemd/environment files were not modified. Coordinator
must apply the proposals before running the expanded tests against production
code. The isolated validation module was removed before commit.

## Reviewable proposals

| Proposal | Resulting behavior |
| --- | --- |
| `01-scheduler-auth.patch` | Grants restricted to the configured repository and Actions read; Actions write selected only when recovery is authorized. Validate token expiry/nonempty token before updating cache. Reject unsafe/symlinked signing-key files. Require RSA PKCS#1 SHA256 signing matching RS256. Disabled/dry-run App clients never mint tokens. GET 401 refreshes at most once; dispatch POST never replays. Persist 403/429 cooldown deadlines. Bound SQLite and flock contention to five seconds, serialize observation/reservation, sanitize state faults, and require a literal boolean alert acknowledgment. |
| `02-environment-contract.patch` | Document repository/App minimum permissions, protected signing-key principal, zero-mint dry-run behavior, and unverified static-token fallback. Defaults remain disabled. |

Both patches passed `git apply --check` against the base. No workflow-enable
endpoint was added. No GitHub App permission permits changing repository flags
or repository contents through this client. GitHub automatically includes
Metadata read; App installation must be restricted to this repository.

## Security findings (P0/P1/P2)

Severity refers to the reviewed implementation and deployment boundary; absence
of a finding does not prove a provisioned host or real credentials are secure.

| Priority | Evidence before proposal | Remediation / remaining requirement |
| --- | --- | --- |
| P0 | No P0 demonstrated by this source/mocked audit. No real credentials or deployed host assessed. | Preserve external activation NO-GO; obtain operational evidence before release. |
| P1 | Token grant `payload={}` inherits all repositories and permissions available to the App installation. | Explicit `repositories: [configured_name]`, `permissions: {actions: read/write}`. Restrict App installation itself to the intended repository and maximum Actions permission. |
| P1 | Disabled/dry-run App path still minted credentials through a POST despite the no-writes contract. | `main` disallows App minting unless both release gates are true and dry-run is false. Supplied token permits GET-only checks; missing App token fails closed as `MONITOR_UNAVAILABLE` without opening the key. |
| P1 | Expired/malformed grants could replace cache fields and get sent to Actions; JWT declared RS256 without constraining OpenSSL key/signature type. | Validate nonempty token and >60 seconds remaining before atomic cache update; RSA PKCS#1 signing option makes incompatible key types fail closed. Mock expiry tests plus a synthetic RSA signature verify the algorithm. |
| P1 | SQLite initialization/cycle failures escaped CLI sanitation; lock acquisition could wait indefinitely. | Five-second SQLite busy timeout and nonblocking flock deadline. Lock spans observation and recovery reservation. Initialization/cycle errors become sanitized `MONITOR_UNAVAILABLE`; state fault report explicitly sets `recovery_state: unknown`. Service/host supervisor must report this when local alert persistence is unavailable. |
| P1 deployment | Baseline inbox/watchdog units use the same UID, which would let a compromised inbox principal access the App key if deployed together as documented. | Coordinator owns the proposed separate inbox UID/group. Provision App key only for the watchdog principal. Template separation is not host provisioning evidence. |
| P2 | 403/429 retried on every timer activation regardless of server cooldown; cached token rejected early by GitHub was not renewed automatically. | Persist Retry-After/primary reset deadlines in `health`; skip API calls until deadline across process restarts. No immediate 403/429 retry. GET 401 refreshes once; POST uncertainty always consumes its original durable reservation. |
| P2 | Protected-key expectation was documentation only; generic sender truthiness could falsely mark a pending alert accepted. | Reject nonregular/symlinked keys, relative paths, group write/execute and all world permissions; service-owned 0600 or root:watchdog 0640 allowed. Sender result must be `is True`. Protected parent directories remain an external requirement. |

The key file is checked before signing but not pinned to an opened descriptor;
an attacker who can modify its parent directory could race replacement. Directory
ownership/mode and a read-only service filesystem are therefore required. An App
key is an installation-wide signing capability: downscoping each token does not
substitute for minimum App permissions and restricted installation selection.

Secrets remain only in process memory and provisioned protected files. Signing
input goes through stdin; private key contents, JWTs, API responses, authorization
headers and webhook URLs are never printed or persisted by the scheduler. Request
redirects remain disabled; reads are bounded to 2,000,000 bytes, HTTP calls to 15
seconds, and OpenSSL calls to ten seconds. Tokens are treated as opaque strings,
including GitHub's changed 2026 token format; no prefix/length assumption exists.

## Renewal and failure evidence

24 targeted unittest cases passed in **5.696 seconds**: ten existing cases and
fourteen added cases. All API/signing mocks used synthetic values; one test
generated a temporary 2048-bit RSA fixture, signed the actual JWT input, and
verified its signature using only its temporary public key. No real key was read.

JWT header is RS256, issuer fixture App ID, issued-at is current time minus 60
seconds, expiration is current time plus 540 seconds. Claims span 600 seconds;
JWT expiration is nine minutes from creation. Installation tokens are cached
only until the 60-second safety margin. A token with 61 seconds remaining uses
cache; at exactly 60 seconds it renews. Expired, blank, null and malformed-expiry
grants raise without replacing the old cache. Failed renewal never returns the
stale token for a request. Normal oneshot timer execution starts a new client
each time, so renewal also occurs on every released invocation without manual
per-edition credential work.

| Scenario | Quantified or asserted result |
| --- | --- |
| App permissions | One configured repository and Actions read/write only in the explicit grant payload; monitor client dispatch rejected before network. |
| GET 401 | One existing-token GET, one mock token grant, one renewed GET, one runs GET; no further retry. |
| Dispatch POST 401 | Exactly one POST attempt, no token grant or POST replay. |
| Metadata 403 / 429 / timeout | One request each; `MONITOR_UNAVAILABLE`, zero dispatch reservations; secret marker absent from report. |
| Rate limit restart | Mock Retry-After 1800s persisted; new process/client at +10 minutes makes zero GETs; +30 minutes resumes with two GETs. |
| Uncertain dispatch restart | Four cycles at +0/+10/+30/+60 minutes produce exactly two durable reservations and two mock POST attempts; both results remain `unknown_or_failed`. |
| Real SQLite contention | Another SQLite connection holds `BEGIN IMMEDIATE`; monitor returns sanitized state outage with zero dispatches and zero sender calls. Test-only busy timeout reduced to 1ms; production proposal stays five seconds. |
| Initial state creation fault | Mock SQLite initialization error yields sanitized JSON and CLI status 1, with no alert call. |
| Disabled / dry-run with App config | Zero signing calls, token grants, database directories, dispatches and alert sends. Supplied read token permits one metadata GET without key/signing access. |
| Truthy nonboolean sink response | Zero accepted alerts; durable status remains pending. |
| Concurrent recovery | Existing two-process fixture in separate temporary Git clones shares one host volume: sum is one recovery reservation and one accepted alert. |
| Release/detection | Existing cases cover `MISSED_RUN`, `RUN_FAILURE`, `WORKFLOW_DISABLED`, `MONITOR_UNAVAILABLE`, delay, duration, main/manual-dry-run filters, 30-minute backoff and two-dispatch ceiling. |

Detection observes Actions execution, not provider freshness or message arrival.
Only the latest due inferred slot is assessed; this is not a history-completeness
claim. At most five pages/500 runs are inspected; truncation reports unavailable.
Dispatch is allowed only for recoverable missing/failed runs of an active workflow,
within six hours of the slot. Disabled workflow, unavailable API, duration-only
and delay-only incidents do not dispatch. Reservations are committed before the
request; crashes/timeouts consume budget. `recovery_state: unknown` on storage
failure means zero *confirmed report count*, not proof no preceding remote
request happened. Accepted alerts prove the configured acknowledgment contract,
not delivery to a device.

## Commands actually executed

```text
# Inside a temporary package containing only the proposed scheduler module:
nice -n 15 env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s ../tests/ranking_alerts -p test_autonomous_scheduler.py -q
# Ran 24 tests in 5.696s; OK.
git apply --check docs/evidence/ops26-watchdog-patches/01-scheduler-auth.patch
git apply --check docs/evidence/ops26-watchdog-patches/02-environment-contract.patch
git diff --check
```

One parent unittest worker was used; the existing bounded concurrency fixture
creates two short-lived subprocesses. No dependency installs/builds, browser
launches, intensive scans, host configuration changes, service starts/enables,
real dispatches, workflows, flags, notifications, WhatsApp calls, secret reads,
issue edits, pushes or main merges occurred. Test slot was released immediately
after the run to the coordinator. Production checks must run after patch
integration; expanded tests intentionally assert the proposed behavior.

## External provisioning and activation requirements

1. Independent Linux/systemd host outside Actions, Python 3.12/OpenSSL, synchronized
   UTC clock, HTTPS egress, protected checkout and persistent local state volume.
   Never install onto the coordinator host while its host review is NO-GO. The
   coordinator reported root usage 94%, approximately 3.15 GiB free, two vCPUs
   and instantaneous contention; this task did not independently probe workload
   capacity or alter resources. No FP&A interference or hardware expansion.
2. App created with maximum Actions read for monitor or Actions write if bounded
   recovery is approved; only this repository installed. Metadata read is
   implicit; no Contents/Issues/administration permission. Provision numeric
   App/installation IDs and RSA key once; key root:atp-watchdog 0640 in protected
   0750 parent, or service-owned 0600. App installation deletion/key revocation
   still requires external repair; renewal is not a remedy for revoked identity.
3. Separate watchdog and inbox service principals; inbox cannot read/sign with
   the App key. Root-owned 0600 environment files, separate durable state
   directories 0700, UMask 0077, NoNewPrivileges/ProtectSystem/ProtectHome and
   fixed service paths. Coordinator owns resource limits and unit changes.
   Baseline timer recurs every ten minutes with persistence and up to 30 seconds
   jitter; exit 1 is journal-observable but treated as successful systemd
   completion. A separate host/journal/heartbeat supervisor must detect the
   watchdog's own failure, disk/lock outage or stopped timer.
4. Independently provisioned authenticated HTTPS operational receiver and
   independent destination, durable idempotency by event ID and literal
   `accepted: true` only after persistence. Verify receipt, replay, restart and
   downstream retry in an authorized staging environment. App credential and
   monitor outages can alert through this channel if host/storage/receiver work.
5. Capacity/disk/retention monitoring and approved budgets before installation.
   Coordinator selected 128 MiB watchdog plus 256 MiB inbox (384 MiB total),
   0.2 CPU combined, CPU/task/I/O limits and 512 MiB planned disk budget; proxy
   incremental capacity is unknown. These are proposal values, not enforced host
   evidence. SQLite uses local disk and shared flock,
   not distributed consensus; different hosts with separate volumes do not
   share the two-dispatch budget.
6. Initial release authorization and coherent external/GitHub flags; templates
   remain false. Recovery needs its separate explicit flag. Workflow remains
   disabled until the coordinator/user's authorized release process changes it;
   this watchdog never enables it. Static PAT fallback needs externally verified
   automated renewal and is not evidence of autonomous App renewal. No weekly
   manual update is required after valid App provisioning, but production outage
   and credential rotation/revocation procedures remain infrastructure duties.

## Official references checked on 2026-10-13

GitHub documents installation token expiry, explicit permission/repository
restriction, and opaque newer tokens:
[installation access token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).
JWT must use RS256 and a short validity horizon:
[App JWT](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app).
GitHub's rate-limit guidance says to honor Retry-After/reset and avoid continued
requests during cooldown:
[REST best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)
and [rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).
Workflow metadata and dispatch permission boundaries:
[workflow REST API](https://docs.github.com/en/rest/actions/workflows).
