# Ops27 independent adversarial review

Date: 2026-10-13 UTC. Original integration: `c05c0e6`, based on
`main@944e417`. Reviewer is independent of implementers A/B/C and the integration
coordinator. Initial review also incorporated coordinator type correction
`ab6db0a` (review-worktree equivalent `9d24ccc`), which did not correct the
behavior below. Reviewer ownership is limited to this report and
`workers/atp-ops/test/adversarial.test.ts`; production corrections belong to the
coordinator.

**Initial result: CODE_NO_GO until the two reproduced P1s below are fixed and
independently rechecked. STAGING_NO_GO and ACTIVATION_NO_GO remain separate.**
This is an incremental review record, not a claim that remote CI passed.

## Scope and evidence boundaries

Read the main-to-integration diff, all Workers source, migration, configuration,
CI and test sources; issue [#33](https://github.com/hmono/Luka-Tennis-Player/issues/33),
draft [PR #32](https://github.com/hmono/Luka-Tennis-Player/pull/32), the three Ops27
implementation/feasibility reports, relevant Ops26 scheduler behavior and prior
independent review. Inspected lockfile pins and registry/integrity records.
Reviewed official D1 transaction/primary-routing and platform-limit contracts.

Synthetic local checks use Node 24.20.0's TypeScript transform and an in-memory
`node:sqlite` shim implementing the D1 calls used by the actual source. Temporary
copies only append `.ts` to local import specifiers. This is **SQLite/source
evidence, not workerd or Cloudflare D1 qualification**. Remote CI must run the
independent tests with the actual migration, Workers runtime and synthetic local
D1. No dependency install, build, heavy suite, production resource, dispatch,
message, key read, VM service, FP&A change, push, issue comment or merge was
performed by this reviewer.

## Reproduced findings

| ID | Severity / initial status | Reproduction and effect | Required correction |
| --- | --- | --- | --- |
| IR-01 | P1, open | Failed production run → newer queued/in-progress retry → failed retry. `runWatchdog` makes every run scope observable; `assessRuns` omits `RUN_FAILURE` for the running replacement. Reconciliation closes the active failure and sends `scheduler:RECOVERED:RUN_FAILURE:1`; when the retry fails, it creates `scheduler:RUN_FAILURE:2`. There was no successful run between the two failures. | Preserve the failure episode until positive completed-success evidence. Suppress recovery dispatch while a replacement runs without reporting the failure recovered. Independent tests cover both queued and in-progress replacements, subsequent failure and completed success. |
| IR-02 | P1, open | Change the durable cycle owner after `reserveDispatch` succeeds, before `client.dispatch`: the superseded isolate still dispatches and writes `result=accepted`. A separate clock advance of ten minutes inside inspection also allows dispatch after the five-minute lease expires with no takeover. Reservation timestamps use invocation-start time, so a four-minute inspection followed by another invocation thirty minutes after the first start permits attempts only twenty-six minutes apart. | Check fresh time/ownership before mutation and immediately before the external POST, including token renewal; consume an ambiguous or abandoned reservation without replay. Fence result writes and use actual reservation time for cooldown/horizon checks. A full cycle deadline must prevent HTTP/D1 latency from outliving its authority. |
| IR-03 | P2, open | SQLite `EXPLAIN QUERY PLAN` reports `SCAN ops_events` for both claim completion lookup and attempt-audit insertion, each using only `WHERE lease_token=?`. Every claim therefore scans retained identities twice, even though health/admission counters are indexed or constant size. | Index the lease lookup or otherwise avoid retained-history scans. Measure actual D1 rows/query counts before using the feasibility cost assumptions. |

The coordinator received the reproduced P1s immediately and was asked to fix
them before technical approval. This review does not classify a hypothetical
platform failure as a reproduced source bug.

Initial native output, using the actual source/migration:

```text
running_retry_invents_recovery:
  midway RUN_FAILURE {active:0,generation:1}
  events RECOVERED:RUN_FAILURE:1, RUN_FAILURE:1, RUN_FAILURE:2
post_after_lease_takeover:
  posts=1; reservation {attempt:1,result:"accepted"}
post_after_lease_expiry_without_takeover:
  elapsed=600000ms; posts=1; reserved_at=invocation_start
claim_lookup_plans:
  SELECT: SCAN ops_events
  INSERT ... SELECT attempt audit: SCAN ops_events
```

Command: `nice -n 15 node --experimental-transform-types
/tmp/ops27-independent-3diqe4df/reproduce.mjs`; elapsed under one second,
exit zero because this diagnostic prints observed behavior rather than asserting
the desired fixed result. These observations are failures of the contracts,
not passing regression results. The permanent independent tests assert the
desired behavior and are expected to fail on the original source.

## Durable state, API and runtime assessment

Inbox acceptance reads, insert/dedup/conflict and acknowledgment data share one
`db.batch`; acknowledgment follows its resolution. The quota trigger aborts an
entire episode/outbox batch. Recovery closure and its outbox insertion use the
same boundary; the independent regression also checks rollback when permanent
capacity is full. Cloudflare documents batch rollback and states that ordinary
database calls remain on the primary unless Sessions are used for replication:
[D1 database API](https://developers.cloudflare.com/d1/worker-api/d1-database/).
This supports the SQL design but does not prove account/storage availability.

Forwarding claims consume attempts durably before network I/O. Four durable
slots bound claims across invocations; token plus expiry fences completion.
Exact immutable payloads survive replay/retirement, and conflicting identities
reject. Lost sink acknowledgment or local completion commits require a genuinely
idempotent downstream service. A second queue alone cannot demonstrate one
visible operator notification. Default twelve-attempt quarantine is explicit
and counted as pending; it needs an external reconciliation/escalation owner.

Minimum GitHub App token requests specify one repository and Actions read, with
Actions write only for recovery-enabled clients. JWT/import/cache renewal and
one-time GET401 retry are synthetic-testable; installation permissions and real
key provisioning remain unverified. No enable endpoint exists. The code makes
ambiguous POSTs single-attempt and durably reserves at most two per slot. IR-02
concerns freshness/fencing of that authority, not a demonstrated third slot
reservation.

GitHub requests have per-operation total deadlines including streamed bodies,
response caps and redirect rejection. Up to six GETs can each incur401, renewal
and replay: a successful worst-case inspection can require nineteen HTTP
operations, before recovery POST and D1 work. Seven requests is the ordinary
path, not a hard total. Fifteen seconds per operation alone does not prove a
cycle finishes before its five-minute lease. Root correction/recheck must cover
that distinction.

Production filtering excludes development and manual dry-run/title-substring
observations. Scheduled runs rely on coherent remote delivery configuration:
the existing ranking workflow can complete a scheduled dry-run while retaining
the production-looking title. The Actions-only App cannot verify repository
variables. A local `DELIVERY_ENABLED=true` value alone cannot certify the remote
workflow actually collected/delivered; activation must verify this coherence
and its change-control/monitoring. Success proves execution, not freshness or
device delivery.

## Capacity, outages and operating limits

Fixed episode scopes, overwritten health state, finite dispatch horizon and
cleanup constrain watchdog storage. Inbox admission caps bound identities,
unresolved events and retained payload; attempts cap audit growth. Payload bytes
are not total database bytes. Exact tombstones retain canonical content, so
retirement does not reclaim payload capacity. Permanent identity/payload quota
eventually returns503 even after successful delivery. No indefinite autonomous
storage claim is justified without a qualified archive/replay protocol.

Backoff and due ordering make progress beyond poison messages; max attempts
prevent perpetual retry by one item. Retained rows still affect claim cost until
IR-03 is fixed. The proposed forty D1 statements per cycle and one hundred rows
read are estimates, not measured runtime bounds. Four attempts alone consume
thirty-six explicit claim/completion statements; watchdog work is additional.
Cloudflare currently documents fifty queries/invocation for Free and one
thousand for Paid, and thirty seconds per query:
[D1 limits](https://developers.cloudflare.com/d1/platform/limits/).
Free admission therefore needs explicit query/CPU proof; Paid still needs
actual rows/storage/billing measurement and abuse budgets.

A total GitHub outage must preserve prior failure state, create one monitor
episode, back off durably and suppress dispatch. Independent tests exercise that
boundary. A total Cloudflare/account outage cannot generate a Worker alert at
all. The documented independent supervisor must run outside both GitHub and
Cloudflare, inspect progress/ages rather than HTTP200 alone, and notify through
an independently qualified path. It is proposed, unprovisioned and untested.

Account403 is evidence of failed authenticated inventory, not proof of account
eligibility. Workers/D1 plan, quotas, runtime CPU/cost, HTTPS, real App, sink,
external monitor and off-provider backup/restore are still NOT_VERIFIED or
UNPROVISIONED. Receiver and watchdog currently share one Worker principal;
the App key isolation risk requires separate minimal bindings/principals or an
explicitly reviewed deployment risk before staging. Restoring old D1 state can
rewind dedup/reservation knowledge and requires reconciliation before enabling.

There is no designed weekly publication/calendar or installation-token renewal
step for a human. Provisioning, quota/archive maintenance, revocation and disaster
recovery still require operational ownership; absence of a weekly step does
not prove those dependencies are ready.

## Gate record

| Gate | Initial independent decision |
| --- | --- |
| Source/code | CODE_NO_GO pending reproduced P1 corrections and independent recheck. |
| Cloudflare deployment feasibility | Not established; account entitlements/consumption and full operating cost remain NOT_VERIFIED. Conditional PoC continuation is not operational GO. |
| Sink / external supervision / restore | NO_GO; contracts and proposals do not substitute for a qualified destination, absence alert or restore exercise. |
| Staging | STAGING_NO_GO. No staging infrastructure provisioned or authorized by this report. |
| Activation | ACTIVATION_NO_GO. All local gates remain false; no production resource/flag, WhatsApp, VM/FP&A, main or PR32 merge is authorized. |

Remote integrated-SHA validation and subsequent correction recheck will be
recorded here separately. No source-only or SQLite result clears operational
gates.
