# OPS-05 / issue #31 — independent adversarial review

Date: 2026-10-13 UTC. Original integration reviewed:
`25c8a94c31b615f090fd2058a93a19c97fc82780`, based on
`944e4174444a32ba7182db62f644e5a433dcee67`. This reviewer was separate from
implementers A/B/C and the integration coordinator. Production corrections
belong to the coordinator; this reviewer owns only this report and
`tests/ranking_alerts/test_ops26_adversarial.py`.

**Final source-review result: TECHNICAL_GO for the corrected code, with zero
open reproduced P0/P1 findings. STAGING_NO_GO and ACTIVATION_NO_GO remain
separate operational decisions.** Initial review withheld technical approval
for three reproduced P1s. Coordinator correction
`3cb3e8d2c02a3019e27ccdaeb45afb5ea67d8184` closed those findings and the Unicode
P2; all seven independent regressions passed. Final integrated-SHA CI remains the
coordinator's responsibility. No installation, host preparation or activation
is authorized.

## Scope and method

Read the base-to-head source/template changes, complete scheduler and receiver,
workflow/release gates, related tests, runbook, all four Ops26 implementation
reports, proposed patches and sink/proxy contract. Traced authentication,
reservations, SQLite commits, acknowledgment loss, restart, deduplication and
monitoring transitions independently before relying on test results. Existing
312-test Python and remote frontend/build success are useful regression evidence,
but did not cover the independent failures below.

All executed repros use synthetic metadata, temporary SQLite or an ephemeral
loopback HTTP server. No real credentials, environment secrets or private keys
were read. No external/production network writes, provider calls, real flags, dispatch, notifications,
service/configuration changes, installations, large copies, host benchmarks,
FP&A changes, pushes, issue comments or merges were performed. Local repros run
serially at `nice -n 15`, with the shared test slot explicitly coordinated.

## Reproduced findings and required disposition

All three P1s were inherited runtime weaknesses, not claims that the Ops26 patch
introduced them. They blocked approval until corrected and independently
rechecked in this same review flow.

| ID | Severity | Evidence on original integration | Owner / disposition |
| --- | --- | --- | --- |
| IR-01 | P1, closed | `GitHubActionsClient.inspect`, original lines 364–372, enumerated all retained history. Five full pages always raised `run_metadata_truncated`, even when the newest run satisfied the current slot. With 500 retained rows, every later cycle reported `MONITOR_UNAVAILABLE`; scheduler observation/recovery could not resume until history changed. | Coordinator fixed in `3cb3e8d`: bound `created` to a two-day UTC window; use `total_count` to recognize an exactly complete page budget. Independent tests pass for old history, exactly 500 recent rows and fail-closed overflow at 501. |
| IR-02 | P1, closed | `_watchdog_cycle`, original lines 392–393, assigned `scheduler:WORKFLOW_DISABLED:<state>` for the entire lifetime. SQLite retains accepted IDs. Disable → healthy/recovered → disable, with restart between observations, sent only the first disable and first recovery. A distinct later outage was silently suppressed. | Coordinator fixed in `3cb3e8d`: persist episode/generation, end it only on observed active state, and preserve the legacy key during an existing migrated episode. Independent restart/recovery test and ack-loss/API-failure continuity test pass. |
| IR-03 | P1, closed | `_request`, original lines 227–233, used a socket inactivity timeout while `response.read(2_000_001)` waited for the body. A sink dripping before each inactivity deadline could hold the inbox's only forwarding worker effectively indefinitely while `/health` remained responsive. | Coordinator fixed in `3cb3e8d`: disposable standard-library HTTP child, anonymous pipes, parent wall deadline, kill and wait on timeout. Independent actual loopback header/body drip tests both expire at the scaled deadline, observe a reaped child, and complete the next request. The watchdog's separate 300s unit limit had not protected the inbox thread. |
| IR-04 | P2, closed | `json.dumps(payload)` defaulted to ASCII escapes. A valid ingress event containing 2000 `é` characters is about 4KiB as UTF-8, but outbound encoding expanded it beyond the identical sink's 8KiB bound. | Coordinator fixed in `3cb3e8d`: UTF-8 JSON with `ensure_ascii=False`. Independent forwarding to an actual loopback 8KiB-limited inbox passes, preserves the exact message, and clears upstream pending state. |
| IR-05 | P2, open | Permanent failures among the first 8 watchdog IDs or first 100 inbox rowids can indefinitely exclude later pending events. Attempt limits bound each flush, not queue fairness. | Runtime owner: fair retry selection before sustained operational use. Existing implementation evidence identified inbox starvation; watchdog selection has the analogous limitation. This is a recorded residual, not a claim that bounded retries ensure eventual progress for all events. |
| IR-06 | P2, open; operational gate | State/IDs grow without safe retention; the health schema lacks oldest-pending age and last successful forwarding progress. Proposed disk budgets and off-host monitoring therefore need further implementation/qualification. | Runtime/storage/monitor owners: age/progress metrics, safe archive/tombstones, retention, quota/backpressure and capacity alarms. Never delete pending work or deduplication history to conceal growth. These gaps keep continuous-operation admission closed. |

The coordinator was notified immediately after IR-01/02 reproduced and was
asked to correct/recheck before technical approval. IR-03 was separately sent
with the real loopback timing observation; IR-04/05 were sent as P2 findings.

## Exact initial reproductions

From this review worktree:

```sh
nice -n 15 env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests.ranking_alerts.test_ops26_adversarial.Ops26AdversarialTests.test_old_history_does_not_permanently_disable_observation \
  tests.ranking_alerts.test_ops26_adversarial.Ops26AdversarialTests.test_a_new_disable_episode_is_delivered_after_recovery_and_restart
```

Result on `25c8a94`: **2 tests, 2 failures, 2.009s**. IR-01 expected active/no
incident with a recent successful run plus 499 old rows; actual workflow state
was `unknown`, with a monitor-unavailable incident. IR-02 expected two distinct
disable alerts; actual accepted list contained one disable and one recovery.
These are expected failing baseline regressions, not a claimed passing suite.

The following IR-03 command is specifically the **baseline-only reproduction
at `25c8a94`**, before the transport was moved to the child. It uses a scaled
inactivity timeout to avoid a long-running host probe. The
transport is the actual urllib transport over loopback; only its configured
15s inactivity timeout is reduced to 0.05s. The peer sends a byte every 0.02s.
No TLS/destination qualification is implied by this transport-only fixture.

```sh
nice -n 15 env PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import json, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from scripts.ranking_alerts.autonomous_scheduler import _request

class Drip(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        body = b'          {}'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        for value in body:
            self.wfile.write(bytes([value]))
            self.wfile.flush()
            time.sleep(0.02)

server = HTTPServer(('127.0.0.1', 0), Drip)
worker = threading.Thread(target=server.handle_request)
worker.start()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
original_open = opener.open
def scaled_open(request, *, timeout):
    assert timeout == 15
    return original_open(request, timeout=0.05)
opener.open = scaled_open
try:
    begin = time.monotonic()
    with patch('scripts.ranking_alerts.autonomous_scheduler.urllib.request.build_opener', return_value=opener):
        result = _request('http://127.0.0.1:%d/' % server.server_port)
    print(json.dumps({'inactivity_timeout': 0.05,
                      'elapsed': round(time.monotonic() - begin, 3),
                      'result': result}))
finally:
    worker.join(2)
    server.server_close()
PY
```

Observed: `{"inactivity_timeout":0.05,"elapsed":0.226,"result":{}}`.
The request succeeded after more than four inactivity periods. A per-socket
timeout is useful but cannot support the implementation report's claim that
all HTTP calls complete within 15 seconds. The Python API explicitly describes
this argument in terms of blocking operations, not a total transaction deadline:
[urllib request documentation](https://docs.python.org/3/library/urllib.request.html#urllib.request.urlopen).

## Credentials, isolation and durability assessment

The integrated changes explicitly request one repository and Actions read, or
Actions write only for configured recovery. This matches the installation-token
downscoping mechanism in [GitHub's token documentation](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).
The installation itself must still be restricted to that repository. Actions
write intrinsically permits additional Actions operations; absence of an enable
call in this client is not a permission-system prohibition on enabling workflows.
Static-token fallback has no automatic renewal implementation.

App cache expiry is checked before request use; 401 read refresh is bounded;
uncertain POSTs are not automatically replayed. JWT claims use RS256 and OpenSSL
RSA PKCS#1 signing. The file check rejects final-component symlinks and unsafe
mode bits. It does not pin an open file descriptor or protect a writable parent
directory: protected root-owned provisioning remains required. Distinct inbox
and watchdog UIDs in templates correctly reduce signing-key exposure. No real
key ownership, App grant, rotation, clock continuity or renewal was qualified.

Both alert hops require authenticated HTTPS, matching identities and literal
boolean acknowledgment. Redirects are rejected. Inbox commit precedes ack;
WAL/FULL and explicit connection closing are present. Recovery intent is durable
before dispatch; uncertainty consumes the same reserved budget. Lock/state
failures fail closed. Crash replay still requires an actually idempotent durable
sink. Ordinary SQLite restart and injected failure tests do not prove physical
power-loss durability, backup recovery, cross-host mutual exclusion or device
delivery. Restoring old state would rewind deduplication/reservation knowledge;
the runbook correctly prohibits doing this as a code rollback procedure.

The off-host supervision requirement is correct and remains unimplemented.
The local watchdog cannot detect total loss of its own host. Inbox HTTP200,
watchdog `SuccessExitStatus=1`, or `last_check` alone do not prove forwarding or
successful GitHub observation. A qualified supervisor must inspect progress and
age, and alert through an independent destination. The current health schema
does not expose oldest-pending age, so additional implementation/instrumentation
is required before satisfying that gate.

## Resource decision and external blockers

I reviewed the calculations and qualifications in the host report; I did not
rerun load probes or claim a new independent host measurement. Reported 3.14GiB
free minus 0.5GiB proposed ATP reserve leaves 2.64GiB, below the proposed 5GiB
minimum by 2.36GiB, before unknown FP&A growth. Two vCPUs, historical load5
3.68 and await near 696ms make RAM availability alone insufficient evidence.
The observed FP&A snapshot failure was pre-existing and its cause is unknown.
No report establishes monthly peak coverage or safe sustained incremental I/O.

The 128/256MiB and 0.1CPU-per-service template limits are proposals, not applied
or benchmarked controls. `IOWeight` is relative priority, not a disk quota.
The 512MiB disk budget lacks enforceable quota, safe retention and demonstrated
growth. A static unit verifier cannot establish FP&A noninterference.

| Gate/dependency | Decision / owner and missing evidence |
| --- | --- |
| Host admission | **HOST_NO_GO**. Host/FP&A owners must establish capacity, monthly peaks, job health, durable storage, isolation and an authorized host. No ONO preparation or hardware expansion in this sprint. |
| Credentials | **UNPROVISIONED**. App owner must install the minimal App, protected key and rotation/revocation procedures; verify real scopes and automatic installation-token renewal. |
| HTTPS | **UNPROVISIONED**. DNS/TLS owner must qualify endpoint, real trust/hostname, proxy bounds and certificate renewal. Loopback fixtures cannot do this. |
| Operational destination | **SINK_NO_GO**. Sink owner must name/qualify the durable idempotent destination and operator-visible channel, including lost ack, restart and outage recovery. A second queue alone is insufficient. |
| Watchdog's own absence | **UNPROVISIONED**. Independent monitoring owner must qualify off-host heartbeat/progress/age/disk/TLS checks and independent notification path. |
| Persistence lifecycle | **UNPROVISIONED**. Storage owner must qualify consistent backup, isolated restore, RPO/RTO, retention/tombstones and capacity controls. |
| Staging | **STAGING_NO_GO**. Code fixes and CI do not substitute for the above staging environment, authorized installation and fault tests. |
| Activation | **ACTIVATION_NO_GO**. Requires separate explicit release authorization tied to reviewed SHA and demonstrated operational gates. No merge/start/enable/send is implied. |

Provisioning is a one-time dependency; ordinary transient API/SQLite/channel
outages should recover without a per-edition or weekly human step. Planned key
rotation, revocation, disk/host disaster, provider-contract change and capacity
maintenance still need named owners and validated automation/escalation.
No indefinite-human-free-operation claim is justified while these dependencies
and growth controls remain open. None should be provisioned against the user's
prohibition merely to convert the gate to GO.

## Independent correction recheck

Read the coordinator's two-file correction `3cb3e8d` independently, including
the new `scripts/ranking_alerts/http_transport.py`. With the coordinator's
explicit authorization, cherry-picked that correction as `bf53221` into this
review worktree for validation; the reviewer did not author production changes.
The child transmits request values only through stdin, suppresses stderr,
limits response-body bytes, rejects redirects and preserves only needed
HTTP status/rate-limit metadata on errors. Parent timeout kills and waits for
the child, covering DNS/connect/header/body stalls without abandoned threads.
Subprocess startup/RSS adds overhead and still needs actual staging measurement
under the proposed cgroup limits; this review does not claim a benchmark.

```sh
nice -n 15 env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.ranking_alerts.test_ops26_adversarial -v
# A seventh test was then added for the new worker's real HTTP error paths:
nice -n 15 env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests.ranking_alerts.test_ops26_adversarial.Ops26AdversarialTests.test_http_worker_preserves_cooldown_and_never_follows_redirect
```

**6 tests passed in 20.176s**, followed by the added targeted worker-contract
test **1 passed in 0.290s**: seven independent tests pass on the corrected source.
The shared test slot was released after each run. No suite/build/install ran
in parallel with these tests. HTTP fixtures clear inherited child credentials/proxy settings,
use only loopback sockets and synthetic tokens, and close their servers.

| Independent check | Observed result |
| --- | --- |
| Current healthy run plus 499 old retained runs | `active`, no incident; historical rows no longer exhaust observation. |
| Exactly 500 / 501 relevant runs | 500 accepted as complete; 501 raises `run_metadata_truncated` without fabricating health. |
| Disable → active → disable, restarting SQLite/client observations | Two distinct disable alerts; disabled workflows never dispatch. |
| Uninterrupted disable plus metadata outage and repeated lost acks | Stable episode identity across all retries/restarts; no unobserved recovery invented. |
| Slow HTTP headers and slow body, independently | Both meet the parent 0.5s test deadline, child is no longer running, later request succeeds. |
| 2000-accented-character event | Exact text reaches bounded durable sink; upstream pending count becomes zero. |
| Actual HTTP429 and redirect through the new child | HTTPError preserves only status and the three cooldown headers; body, token, URL and private header are absent from the error. HTTP302 does not request its Location target. |

No reproduced P0/P1 remains open. Technical source review is **GO** at the
corrected source, with the stated P2 residuals. Host, sink, staging and activation
decisions remain **NO_GO**; source approval cannot remove the user's prohibition
on provisioning. Final integrated-SHA regression CI belongs to the coordinator.

Original remote CI supplied by the coordinator was successful at `25c8a94`:
[ATP Ranking Release Checks](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38457571977)
(312 Python tests plus 81 frontend tests and build) and
[CI](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38457571955).
That evidence applies to the original SHA. The independent recheck above clears
the reproduced code failures; neither evidence set establishes infrastructure
readiness or authorizes release.
