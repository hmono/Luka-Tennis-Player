# ATP Ops27: local Workers + D1 proof of concept

This package is an isolated, disabled prototype. It does not provision or deploy
Cloudflare resources, enable ATP, modify Pages or deliver real messages.
See [the integration evidence](../../docs/evidence/ops27-integration.md) for the
reviewed revision, actual test runs and independent release decisions.

## Validation

Run on an isolated CI runner (not the constrained ONO VM):

```sh
cd workers/atp-ops
npm ci
npm run typecheck
npm run migrate:local
npm run migrate:local # no outstanding migrations on the second run
npm test
npm run check:bundle # dry-run bundle only; does not upload
```

The pinned test toolchain runs TypeScript inside workerd with synthetic local D1.
`test/setup.ts` resets bindings and reapplies the actual migration before each
test. The configuration contains a fabricated database UUID, `remote: false`,
no account, route, secret or active Cron Trigger. There is no deploy script.
`node_modules`, Wrangler state and local credentials are ignored.

The candidate future Cron expression is `*/10 * * * *` (UTC). Installing it,
creating a real D1 binding and enabling any network behavior require separate
authorization after staging qualification. Do not substitute a production
database UUID into this local configuration.

## State and acceptance

`POST /events` accepts the Ops26 contract `{event_id, message}` with a dedicated
bearer credential. Only a durable commit permits `{accepted:true,event_id}`.
Identical replays preserve one row; conflicting payloads are rejected. Optional
`kind` is ignored as specified by the earlier sink contract. Acknowledgment
proves queue acceptance, never device arrival or operator attention.

D1 v1 tables include the immutable event ledger, forwarding leases, bounded
attempt audit, admission limits/counters, watchdog state, failure episodes and
dispatch reservations. Trigger-based capacity checks roll back the entire batch
when the inbox cannot persist a new event. Episode and outbox insertion share
that transaction. No read replication is enabled for correctness-sensitive state.

Default admission caps are 10,000 identities, 1,000 unresolved events and 8 MiB
of canonical payload. These are PoC safety budgets, not measurements of total
database storage or actual account eligibility. Index/audit/SQLite overhead and
other account workloads must be measured separately. Four durable forwarding
slots bound cross-isolate concurrency. Backoff and attempt budgets prevent a
poison event from indefinitely occupying the first position in a queue.

Retired forwarded events keep canonical payload and dedup identities. Pending
and quarantined events are never silently deleted. Deletion is denied by schema;
an external archive/restore protocol must be qualified before changing this.
Capacity exhaustion yields explicit backpressure. It is observable and safe,
but it is not proof of indefinite autonomous operation with finite storage.

## Provisioning remains external

Required: verified Workers/D1 plan and headroom, separately authorized staging
account/database, trusted HTTPS endpoint, minimal repository-scoped GitHub App,
dedicated runtime secrets, qualified idempotent operational sink, an independent
monitor outside both GitHub and Cloudflare, and backup/restore exercises.

The external monitor must validate authenticated health including cron age,
successful observation age, backlog age, forwarding progress and quarantines.
An HTTP 200 alone is insufficient. It must alert on absent/failed probes through
an independently hosted notification path. This closes the complete-Cloudflare
outage blind spot only after the independent service is actually qualified.

No normal ATP publication or installation-token renewal should require a weekly
human action once provisioned. Credential revocation, disaster recovery, billing
and provider contract changes still need named operational owners. No service
outside synthetic CI is homologated by these tests.

## Source references

- [Workers Vitest integration](https://developers.cloudflare.com/workers/testing/vitest-integration/)
- [D1 local development](https://developers.cloudflare.com/d1/best-practices/local-development/)
- [D1 migration lifecycle](https://developers.cloudflare.com/d1/reference/migrations/)
- [Ops26 reference, without merging PR32](https://github.com/hmono/Luka-Tennis-Player/pull/32)
