# OPS-03 — proposed durable sink adapter contract

Status: `SINK_NO_GO`. This is a reviewable adapter design, not a configured or
qualified delivery channel. No operator destination, endpoint, credential or
provider account was provisioned or exercised.

The upstream inbox is independent of GitHub Actions and accepts synthetic or
operational events through authenticated HTTPS. A downstream adapter must be an
independent persistent queue, with an operator-visible channel behind it. A queue
that forwards into another queue indefinitely does not establish operator reach.
The proposed receiver can provide this adapter's durable ingress and retry queue;
its actual provider integration remains an external deployment decision.

## Wire contract

- Endpoint: `POST /events`, HTTPS with a trusted certificate; authenticated with
  `Authorization: Bearer <separate sink token>`. Disable redirects.
- Request: JSON object `{"event_id":"<stable identity>","message":"<text>"}`.
  `event_id` is 1–256 Unicode characters; `message` is 1–4096 characters; the
  **entire encoded request is at most 8192 bytes**. Optional upstream `kind` may
  be ignored. The sender also supplies the existing `Idempotency-Key` header,
  `SHA256(event_id UTF-8)`, but the body identity is the persisted primary key.
- Success: HTTP 200 with the JSON object
  `{"accepted":true,"event_id":"<same identity>","duplicate":false}`. Replay of
  the same identity and exact message returns the same success with `duplicate`
  true. Boolean true and a matching identity are both required by the proposed
  forwarding adapter. Empty HTTP 2xx, text, numeric 1, false, missing identity and
  mismatching identity never remove the upstream pending event.
- Changed payload under an existing identity: HTTP 409
  `{"error":"event_id_conflict"}`; preserve the original message. Surface the
  persistent error to the sink owner; automatic retries never overwrite it.
- Invalid JSON, framing, shape or bounds: 400; wrong media type: 415; wrong
  credential: 401; wrong path: 404. No positive acknowledgment on these responses.
- Storage unavailable or worker capacity exceeded: 503 with a generic code and
  `Retry-After: 1`; partial-body read timeout: 408. Queue retries may use a longer
  interval than Retry-After. No exception detail, credentials or message body in
  logs or diagnostic responses.

## Durable adapter state and recovery

1. Authenticate, validate and bound the body before touching provider APIs.
2. Begin the local SQLite transaction on a persistent local filesystem; use WAL
   and `synchronous=FULL`; reserve immutable `event_id` and message in a pending
   row. Replays read and compare the already committed content.
3. Commit and close the database connection before emitting accepted true. Any
   commit/fsync failure has no positive acknowledgment. Keep the DB, `-wal` and
   `-shm` files on the same protected persistent volume; do not copy only the
   live `.sqlite3` file as a backup.
4. A separate bounded worker commits each attempt before a network operation.
   Restart or lost acknowledgment replays exactly the same identity. Only a
   qualified idempotent next hop can make this retry safe. A generic messaging
   webhook or provider acknowledgment alone does not qualify that hop.
5. Record next-hop durable acceptance separately from `operator_delivered`.
   The current `forwarded=1` means only that a qualifying next hop accepted the
   event; it makes **no claim of device arrival, reading or human response**.
   Add provider receipt IDs and authenticated delivery callbacks only after a
   selected provider documents and passes its actual contract. Unknown delivery
   remains unknown; never invent a delivery receipt from an HTTP success.

If the chosen operator channel does not deduplicate stable IDs, this generic
retry worker cannot safely be connected directly. The concrete provider adapter
must choose and document its uncertainty policy and operator escalation path;
that missing integration keeps the gate `SINK_NO_GO`. Do not wrap CallMeBot or an
unqualified webhook by simply translating any HTTP 2xx into accepted true.

## Qualification still required

An owner must name the independent destination and actual operator-visible
channel, provision separate credentials without committing them, and demonstrate
persistent-volume durability, restart recovery, identity conflict rejection,
ack-loss replay, channel unavailability and eventual recovery. Confirm reach to
the intended operator through a separately authorized controlled test. Record
queue acceptance and device/operator evidence as different results. Also define
credential rotation, queue age and backlog monitoring, disk-full alarms, backups,
retention and retry fairness. No provider-specific claims are made here.

Compatibility: the proposed stricter schema is new. Existing destinations that
only return accepted true must be upgraded/qualified before activation. The
watchdog's `webhook_sender` can consume the augmented inbox response, but the
coordinator should harmonize its destination/token validation and matching-ID
check with `forward_sender`. The sender transport currently reuses `_request`
with GitHub-oriented Accept/version headers, a 15s network timeout, response
limit 2,000,000 bytes and redirect rejection. A selected sink must tolerate those
headers or the coordinator must introduce a dedicated JSON transport; a provider
adapter must not silently depend on GitHub API response semantics.
