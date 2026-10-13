# Sprint #25 A — publication-driven collection

Scope: issue #25, built from `dc5032a`. Source acquisition and sports facts only;
delivery recovery, weekly status and scheduler monitoring are integrated by the
other sprint components. No provider requests, deployment, workflow enablement,
secret changes or real WhatsApp messages were performed for this component.

## Operational contract

`collect()` and `dry_run()` now use `assess_observation()` by default. They never
read the calendar in this mode. A fully validated source date that strictly
advances the last persisted date is `FRESH`; repeating that date is
`NO_NEW_EDITION_OBSERVED`, regardless of its age or calendar horizon. An initial
verified edition is accepted with its declared date, even when old. Nothing
asserts that ATP had no edition or that a repeated old ITF edition is stale ATP.
Publication date and check time remain separate. An off-Monday advance is valid.

Future dates, source regressions, inconsistent singles/doubles dates, HTTP and
identity errors are `SOURCE_ERROR` and cannot change sporting data. Normalized
source replies recover automatically on the next scheduled collection. Retry
scheduling and technical messages are the runtime's responsibility. `SOURCE_LAG`
is reserved for evidence from a qualified later source; no alternative source
has been qualified or enabled in this component.

The shared assessment retains compatibility fields. In publication mode,
`expected_date` means the observed/last verified date (or check date if there is
no usable date), `cutoff` is the check timestamp, and `calendar_version` is
`publication-driven-v1`. They are not predicted publication deadlines.
Passing an explicit `calendar=` or `--calendar-path` retains legacy behavior for
historical compatibility tests. The legacy `deliver` command remains isolated
from the new autonomous delivery runtime and retains its old gate.

`CollectionOutcome.source_telemetry` provides allowlisted provenance for the
runtime journal: ATP `B0UF`, ITF `800625103`, fixed public profile URL, HTTP
statuses, acquisition timestamps, per-discipline declared dates/ranks and safe
cache metadata. Raw bodies, arbitrary DOM text, headers and cookies are excluded.
The fixed API endpoints and crosswalk remain versioned in `itf_source.py`.
Live identity requires the exact profile URL, an exact known page title and an
exact athlete heading. Arbitrary athlete-name prefixes are rejected. Both
disciplines must independently declare the same edition. ITF points stay null.

Each advancing edition creates a `weekly_digest`, including unchanged ranks.
Repeated observations create neither a snapshot nor another digest. Same-edition
corrections append snapshots and replace pending intentions through existing
supersession references; accepted receipts remain unchanged. Career highs use
the validated baseline and effective edition history, so withdrawing an erroneous
rank also retracts its derived high without rewriting past audit snapshots.

New correction IDs bind ranking facts to the immutable predecessor. Legacy
content-addressed IDs still load unchanged. Validation requires a same-date,
already-existing parent; new chains must extend the latest revision. This supports
A → B → A → B corrections without permanent manual reconciliation. A pending
correction B is superseded if the source returns to previously delivered A, so
withdrawn B cannot remain eligible to send.

## Evidence

`test_publication_driven.py` exercises 56 consecutive daily checks across eight
weeks, past the existing calendar horizon, with the calendar loader patched to
fail on any access. The old edition remains `NO_NEW_EDITION_OBSERVED`, both files
remain byte-identical, and a delayed Tuesday publication of equal ranks creates
one digest. Further checks remain idempotent. This test covers collection only;
weekly status uniqueness is exercised by the integrated runtime suite.

Additional tests cover mismatched discipline dates and identity followed by
automatic recovery, null points and safe provenance, A → B → A → B history and
CH retraction, preservation of accepted receipts, supersession of withdrawn
pending corrections, legacy revision loading, and rejection of missing,
cross-edition, forward, self-referential or obsolete revision parents.

Validation: `python3 -m unittest discover -s tests/ranking_alerts -p 'test_*.py' -q`.
The final complete regression passed **246 tests** in 44.9 seconds. No external source was
contacted by these deterministic tests. The integrated sprint performs the real
read-only dry-run and frontend/build checks separately.
