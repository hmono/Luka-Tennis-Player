# OPS-03 / issue #29 — independent operations inbox audit

Date: 2026-10-13 UTC. Audited repository base: `944e417` on isolated branch
`ops26/ops-inbox`. Result: repository hardening is reviewable and synthetic tests
pass with the proposed patch. **`SINK_NO_GO`; HTTPS ingress is not qualified;
activation remains blocked.** The coordinator also reported `HOST_NO_GO` on this
host because the root filesystem is 94% full and the two vCPUs are contended.

Only `tests/ranking_alerts/test_ops_receiver.py` and this evidence directory were
changed. Shared production changes are supplied as
[`0001-receiver-hardening.patch`](ops26-inbox-patches/0001-receiver-hardening.patch).
An isolated minimal Python copy under the worktree exercised that proposal; it
was removed before committing. No host installation, nginx reload, unit
start/enable, DNS/firewall change, real event, WhatsApp send, credential read,
workflow/flag activation, push or merge was performed. All tokens and messages in
tests are explicitly synthetic; all sockets are ephemeral loopback sockets.

## Findings and proposed behavior

| Priority | Observation on base | Proposed result / remaining requirement |
| --- | --- | --- |
| P0 gate | No newly reproduced P0 code defect. Host, HTTPS and actual destination are unqualified. | Continue NO-GO. Repository test results cannot authorize activation or prove operator delivery. |
| P1 | `ThreadingHTTPServer` has unbounded request threads and no socket/body timeout. Authorized partial bodies can hold workers indefinitely; a burst can exhaust a contended host. | Four HTTP workers, backlog eight, 5s socket timeout, generic overload 503 and partial-body timeout 408. A proxy must also limit clients/rate/body/header timing. |
| P1 | Acceptance/health SQLite failures escape the HTTP handler; the client gets a dropped connection and the default server may print traceback details. | Sanitized storage 503 with Retry-After, startup/bind error codes, suppressed error tracebacks. Never acknowledge a failed commit. |
| P1 contract | Forwarding checks only accepted true; it does not bind the acknowledgment to the requested identity. Destination validation checks only scheme and forwarding token can be empty. | Authenticated valid HTTPS destination, reject userinfo/fragments/control whitespace, require **accepted is true plus matching event_id**. Upgrade/harmonize all sending adapters before activation. |
| P2 | `synchronous=FULL` is already set; the actual journal is `delete`, not WAL. SQLite connection context managers commit but do not close their owned connection. | Initialize WAL, retain FULL on each connection, explicitly close every owned connection, fsync inbox directory before accepting traffic. DELETE/FULL was not shown to lose committed rows; absence of WAL is a concurrency/configuration gap. |
| P2 | Conflict rejection exists but is returned as generic 400. Non-ASCII authorization can make the string compare raise. JSON scalars, duplicate Content-Length/transfer encoding and deeply nested payloads need explicit handling. | Explicit conflict409, byte-based constant-time bearer comparison, JSON-object/type/media bounds, reject ambiguous framing and truncated EOF, catch nested-input recursion errors. |
| P2 operations | Queue retention, oldest pending age, disk-full supervision and destination qualification are absent. First 100 FIFO pending rows can starve newer rows if those 100 fail permanently. | Provision backlog/age/disk alarms and backup policy on an isolated host; coordinator should add retry fairness and a selected provider policy before release. No retention deletion was introduced. |

The existing accept transaction already exits its SQLite commit context before
returning, so this audit did not find a pre-commit accepted true on the base.
The proposal makes that order explicit. Both base and proposal require strict
boolean forwarding acceptance and preserve pending work on transport failures.
The forward loop already survives a SQLite error and retries from disk; tests
preserve that behavior with a real write lock and automatic recovery.

## HTTPS and proxy audit (read only)

The receiver's production bind is `127.0.0.1:8765`; HTTPS must terminate at a proxy.
Read-only inspection found `/usr/sbin/nginx`, an enabled stock default site on
port80, no TCP443 listener, and no receiver listener on8765. Inspected only nginx
configuration text and listener metadata; no certificates, private keys,
environment secrets, logs or public endpoints were read. The inspected global
nginx config allows legacy TLS versions, while the stock site has its SSL block
commented out. These observations are insufficient to qualify secure ingress.

[`nginx-inbox.conf.proposed`](ops26-inbox-patches/nginx-inbox.conf.proposed) is an
uninstalled candidate with reserved `.invalid` hostname and unusable certificate
placeholders. It adds TLS1.2/1.3, an 8KiB body bound, buffered upstream bodies,
client/rate limits, timeouts, bearer forwarding and no body/access logging. It
cannot be activated until an isolated host, DNS ownership, trusted certificate,
firewall and monitoring have been provisioned and separately authorized. The
candidate was reviewed as text; no nginx configuration or live proxy was changed
or validated with a fabricated certificate.

## Destination contract and adapter proposal

The exact proposed success response is
`{"accepted":true,"event_id":"<matching event_id>","duplicate":false}` after
successful durable commit; a matching replay returns duplicate true. Reusing an
identity with a different message is409 and never overwrites the original. HTTP
2xx alone, missing/mismatching identity, false and numeric1 cannot mark a row
forwarded. `forwarded=1` means next-hop durable acceptance, with no claim about a
device, an operator reading it, or final delivery.

The complete transport, durability, uncertainty and qualification contract is
[`durable-sink-adapter-contract.md`](ops26-inbox-patches/durable-sink-adapter-contract.md).
The receiver itself can be the ingress of an adapter with a durable queue, but
there is no selected operator-visible channel or provider integration. Replacing
that missing integration with another queue is insufficient. **`SINK_NO_GO`**
persists until a named owner and destination demonstrate the contract and actual
channel evidence under separately authorized controlled testing.

Compatibility changes for the coordinator: forwarding now requires a separate
nonempty `ATP_OPS_FORWARD_TOKEN` and matching acknowledgment identity. The
augmented receiver response remains compatible with the watchdog's existing
accepted:true check, but that watchdog should adopt the same identity/token/URL
validation before release. No existing destination was assumed to implement the
new schema. The shared `_request` still sends GitHub-oriented headers; coordinate
a dedicated JSON transport if the selected sink requires one.

## Verification and resource use

[`proposal-tests.txt`](ops26-inbox-patches/proposal-tests.txt): **17 tests passed**
on the isolated proposal with Python3.12 and SQLite3.45.1. Run at `nice -n15`, one
unittest suite at a time, after coordinator released the shared test slot. Final
run:3.072s unittest /3.47s elapsed,14% aggregate CPU,29,944KiB peak RSS. An earlier
16-test run passed before added boundary/recursive-input checks (7.423s unittest).
The only setup error was a missing copied domain module; copying that existing
module resolved it without installation or production edits.

Coverage includes restart dedup and immutable conflicts; WAL/FULL and explicit
connection closes; real SQLite write locks and forward-loop survival/recovery;
unavailable destination; timeout after the synthetic durable sink commits;
restart replay after next-hop acceptance but failed local marking; strict
acknowledgment identity; invalid forward configuration making no request;
auth/path/media/JSON/size/character bounds; partial-body timeout and truncated EOF;
ambiguous framing; storage503; commit-failure rollback without accepted true;
independent connection visibility after acknowledgment; and worker overload.
The synthetic durable sink uses a separate temporary SQLite inbox, so the
ack-loss test demonstrates one persisted sink row despite two attempts. No test
asserts device or human delivery.

[`baseline-regressions.txt`](ops26-inbox-patches/baseline-regressions.txt): three
selected future-contract tests ran against **untouched production code** and
failed as expected (six assertions): journal `delete` instead of `wal`, missing
matching-ID enforcement, and transport reached despite malformed URL,
userinfo/fragment or empty token. Exit1 is intentional baseline evidence, not a
claimed passing build. Other new HTTP tests depend on the proposed bounded
server; the coordinator must apply the patch when integrating these tests.
`git apply --check` passed on base; a full project suite belongs to integration.

The tests exercise real local commit/restart and lock behavior plus an injected
commit/fsync failure; they do not simulate a physical power cut or establish the
host filesystem/hardware fsync contract. Current resource evidence is test-only,
not a production capacity measurement. Expected idle footprint is one small
Python service (~30MiB test peak), one forwarding thread, at most four HTTP
workers and SQLite files; a provisioned unit still needs measured memory/CPU/FD
caps. Each full ASCII event uses roughly4.5KiB plus SQLite/index/WAL overhead;
1000 maximum-size events therefore require at least several MiB, and indefinite
outage means unbounded disk growth without a separate capacity/retention policy.
No large repository copy, dependency install, build or host modification occurred.

## External blockers

1. An isolated host with sufficient durable disk headroom and measured resource
   limits; the current host's reported HOST_NO_GO remains controlling.
2. A provisioned trusted HTTPS endpoint and proxy/firewall qualification. Loopback
   HTTP tests do not validate TLS, certificate lifecycle or network independence.
3. A named independent destination, dedicated credentials and a provider adapter
   that implements durable idempotency plus a defined uncertainty policy.
4. Separate proof of operator/channel delivery, queue-age/backlog and disk-full
   monitoring, backups, secret rotation and restart supervision.
5. Coordinator integration of the shared patch and watchdog contract validation;
   production units, flags and workflows remain disabled until all release gates
   and authorization are satisfied.
