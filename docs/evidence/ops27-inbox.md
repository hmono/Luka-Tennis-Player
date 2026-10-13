# Ops27 inbox PoC — synthetic engineering evidence

Date: 2026-10-13 UTC. Base: `944e417`; isolated branch `ops27/inbox`.
Scope: issue [#33](https://github.com/hmono/Luka-Tennis-Player/issues/33),
draft [PR #32](https://github.com/hmono/Luka-Tennis-Player/pull/32), Ops26 inbox
audit, independent review and durable sink contract read before implementation.
No dependency installation, production provisioning, dispatch, actual sink
request, message, credential, VM service or FP&A change occurred.

## Durable contract and exported integration

`handleInboxRequest(request,{repository,token,...})` implements authenticated
`POST /events` and `GET /health`. Ingress bounds UTF-8 JSON to 8192 bytes, identity
to 256 Unicode characters and message to 4096 characters. Optional `kind` is
ignored as in the Ops26 contract. Canonical identity is exact
`JSON.stringify({event_id,message})`, preserving the complete immutable payload.
Accepted acknowledgments include matching `event_id` and `duplicate`, and are
created only after a successful D1 transaction. Concurrent same-ID accepts have
one original acknowledgment; changed payloads return409. Capacity/storage failure
returns generic503. Body deadline defaults5s; commit/status response deadline5s.
A response deadline cannot cancel D1; a late commit remains deduplicated and is
recovered by a matching replay.

`enqueueStatement(db,event_id,message,now,guard?)` allows the watchdog episode and
incident outbox insert to share one transactional `db.batch`. Guard SQL and
bindings are trusted internal code, for a durable watchdog lease predicate.
Canonical conflicts violate a NOT NULL constraint; new-event capacity is enforced
by the coordinator migration's aborting trigger. Either failure rolls back the
entire batch. A guard that does not match makes no insert; the caller must use
the same fence on its episode writes. No provisional episode acknowledgment is
invented by this factory.

`InboxRepository(db,options?)` exports `accept`, `claimDue`, `finishAttempt`,
`status`, and `retainForwarded`. All attempt claims commit before a network call.
Up to four database slots bound simultaneous forwarding across invocations;
token and expiry predicates fence late completion. A crash consumes its durable
attempt and expires into retry selection. Due time and backoff let later events
progress beyond poison messages. Default attempt budget12 ends in explicit
quarantine, included in pending count and oldest-age metrics. Quarantine preserves
the event and audit; a qualified reconciliation/escalation path remains necessary
before activation.

`forwardDue(repository,options)` bounds one batch to4 attempts by default
(maximum16), each full HTTP transaction to10s (maximum15s), and responses to8192
bytes. It rejects redirects and malformed/non-HTTPS/userinfo/fragment destinations,
requires a separate token, and sends SHA256 identity as `Idempotency-Key`.
Only strict `accepted === true` and exact matching identity clear pending.
HTTP errors,429, timeouts, oversized/invalid/mismatching acknowledgments remain
pending with durable exponential backoff. Next-hop acknowledgment does not imply
operator/device delivery. The coordinator production entrypoint must retain its
false forwarding/activation gate; synthetic tests explicitly inject enabled mocks.

## Metrics, retention and bounded growth

The coordinator owns the migration, centralized limits and transactional counters.
Admission and health totals use maintained O(1) counters. Oldest age uses three
indexed state-specific first-row queries; health does not scan the entire audit.
Health includes oldest pending age, successful-forward progress/time, last attempt,
durable attempts/failures, leased/quarantined work, identity/payload/audit growth,
and configured quotas. Times/ages are milliseconds; delivery remains `unknown`.

Default centralized capacity:10000 permanent identities,1000 unresolved events,
8MiB retained canonical payload. Quarantined work consumes unresolved capacity;
matching replays continue to succeed at capacity. `retainForwarded` marks accepted
old events as tombstones and records audit without deleting their exact canonical
content. Pending, identities and audit are never removed. Deletion is denied by
the migration. This intentionally does not reclaim message bytes: exact replay
proof persists. Event and attempt cardinality are bounded, but payload quota is
not a measured database-byte budget; indexes/audit/backups add overhead. Eventually
permanent dedup identities fill capacity and new ingress receives explicit503.
A separately qualified archive/replay protocol and monitoring are still required
for continuous operation. No claim that TTL resolves indefinite growth is made.

Cloudflare documents D1 batch rollback on statement failure in its
[D1Database API](https://developers.cloudflare.com/d1/worker-api/d1-database/).
That platform contract is relied upon for commit ordering, capacity rollback and
episode/outbox atomicity; local SQLite checks do not establish remote durability.

## Executed versus pending validation

Executed on ONO without installing dependencies:

- Four `nice -n15 node --experimental-transform-types --check` checks: repository,
  ingress, forwarding and test source; all exit0 with Node24.20.0.
- `git diff --check`: exit0.
- One lightweight native `node:sqlite` in-memory smoke with the actual exported
  TypeScript and coordinator migration: passed. Checked concurrent acceptance,
  immutable conflict, durable retry/restart,429 backoff, retirement/replay,
  deletion rejection, full rollback of watchdog state when admission is full,
  HTTP503 on capacity, poison fairness, quarantine and persistent metrics.
  This is a small SQLite API shim, **not Miniflare or Cloudflare D1 evidence**.
  Temporary smoke files are outside the repository; no production database used.

Not executed here: Vitest Workers tests, TypeScript typecheck, Miniflare real local
D1, remote CI, or remote D1. `test/inbox.test.ts` supplies real-local-D1 cases for
the coordinator's remote CI, using its per-test reset/migration setup and only
synthetic fetch implementations. Includes same-ID concurrency, ingress response
loss, episode/outbox capacity/conflict rollback, stale guards, delayed/failed
commit, auth/bounds/partial-body deadline, Unicode forwarding, six invalid-ack
variants, four HTTP failures/429, fetch/body deadline, response cap, poison-head
fairness, durable slot concurrency/fencing, sink commit/ack loss plus failed local
mark/restart replay, interrupted final attempt, exact tombstones/audit, and false
configuration gates. The ack-loss mock durably stores sink IDs in a distinct
synthetic D1 table; it asserts one sink event across three attempts.

**Implementation review candidate; remote test execution pending. SINK_NO_GO /
STAGING_NO_GO / ACTIVATION_NO_GO.** No account entitlement, trusted HTTPS ingress,
provider delivery, operator reach, external watchdog or infrastructure durability
is established by this PoC.
