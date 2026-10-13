#!/usr/bin/env python3
"""Collect ATP rankings and deliver durable WhatsApp alert intentions."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from contextlib import nullcontext
from uuid import uuid4

from ranking_alerts.atp_source import AtpSourceError, load_fixture
from ranking_alerts.career_high import (
    DEFAULT_BASELINE_PATH,
    CareerHighBaselineError,
    enrich_with_baseline,
)
from ranking_alerts.domain import (
    OutboxItem,
    DisciplineRanking,
    DomainValidationError,
    RankingAlertState,
    RankingDelta,
    RankingObservation,
    RankingSnapshot,
    RankingsData,
    build_snapshot,
    compare_snapshots,
    event_id,
    format_message,
    snapshot_sort_key,
)
from ranking_alerts.source import RawRankingObservation, RankingSource, RankingSourceError
from ranking_alerts.freshness import (
    DEFAULT_CALENDAR_PATH,
    CalendarError,
    EditionCalendar,
    FreshnessAssessment,
    FreshnessState,
    assess_publication,
    assess_observation,
    load_calendar,
    utc_now,
)
from ranking_alerts.telemetry import append_summary, emit_collection_summary, emit_schedule_summary, schedule_timing, safe_source_telemetry
from ranking_alerts.providers import (
    CallMeBotProvider,
    ConfigurationError,
    DeliveryError,
    NotificationProvider,
    validate_callmebot_config,
)
from ranking_alerts.storage import (
    StorageError,
    load_alert_state,
    load_rankings,
    save_alert_state,
    save_rankings,
)
from ranking_alerts.incidents import (
    DEFAULT_INCIDENTS_PATH, deliver_incidents, load_incidents, pending_incidents,
    plan_recovery, plan_stale, plan_source_error, save_incidents, format_incident,
    unresolved_deliveries,
)
from ranking_alerts.collection_transaction import recover_collection, save_collection
from ranking_alerts.durability import GitCheckpoint, STATE_PATHS, state_lock

DEFAULT_RANKINGS_PATH = Path("data/rankings.json")
DEFAULT_STATE_PATH = Path("automation/state/ranking_alerts.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True, kw_only=True)
class CollectionOutcome:
    snapshot_status: str
    outbox_status: str
    rankings: RankingsData
    state: RankingAlertState
    snapshot: RankingSnapshot
    delta: RankingDelta | None
    freshness: FreshnessAssessment | None = None
    source_telemetry: dict[str, Any] | None = None


def _latest_for_date(snapshots: Sequence[RankingSnapshot], ranking_date: str) -> RankingSnapshot | None:
    candidates = [snapshot for snapshot in snapshots if snapshot.ranking_date == ranking_date]
    return max(candidates, key=snapshot_sort_key) if candidates else None


def _previous_date_snapshot(
    snapshots: Sequence[RankingSnapshot], ranking_date: str
) -> RankingSnapshot | None:
    previous_dates = {snapshot.ranking_date for snapshot in snapshots if snapshot.ranking_date < ranking_date}
    if not previous_dates:
        return None
    return _latest_for_date(snapshots, max(previous_dates))


def _snapshot_date_by_id(rankings: RankingsData) -> dict[str, str]:
    return {snapshot.id: snapshot.ranking_date for snapshot in rankings.snapshots}


def _sort_outbox(state: RankingAlertState, rankings: RankingsData) -> RankingAlertState:
    dates = _snapshot_date_by_id(rankings)
    return RankingAlertState(
        schema_version=state.schema_version,
        outbox=tuple(sorted(state.outbox, key=lambda item: (dates[item.snapshot_id], item.created_at, item.id))),
    )


def _same_sporting_content(snapshot: RankingSnapshot, observation: RankingObservation) -> bool:
    """Compare ranking facts while deliberately ignoring provider provenance."""

    return (
        snapshot.ranking_date == observation.ranking_date
        and snapshot.singles == observation.singles
        and snapshot.doubles == observation.doubles
    )


def plan_collection(
    rankings: RankingsData,
    state: RankingAlertState,
    observation: RankingObservation,
    *,
    captured_at: str,
) -> CollectionOutcome:
    same_date = [item for item in rankings.snapshots if item.ranking_date == observation.ranking_date]
    latest_same_date = max(same_date, key=snapshot_sort_key) if same_date else None
    if latest_same_date is not None and _same_sporting_content(latest_same_date, observation):
        return CollectionOutcome(
            snapshot_status="unchanged",
            outbox_status="none",
            rankings=rankings,
            state=state,
            snapshot=latest_same_date,
            delta=None,
        )

    candidate = build_snapshot(
        observation,
        captured_at,
        source_revision_of=latest_same_date.id if latest_same_date is not None else None,
        chain_revision=True,
    )

    existing = next((item for item in rankings.snapshots if item.id == candidate.id), None)
    if existing is not None:
        # A revision is identified by its facts and immutable predecessor.
        # Replaying a previously persisted chain must never re-order history.
        raise RankingSourceError("ranking_source_schema_changed")

    snapshot_status = "revised" if latest_same_date is not None else "created"
    snapshots = tuple(sorted(rankings.snapshots + (candidate,), key=snapshot_sort_key))
    updated_rankings = replace(rankings, snapshots=snapshots)
    previous = _previous_date_snapshot(rankings.snapshots, candidate.ranking_date)
    history = tuple(item for item in rankings.snapshots if item.ranking_date < candidate.ranking_date)
    delta = compare_snapshots(previous, candidate, history) if previous is not None else None
    dates = _snapshot_date_by_id(rankings)
    sent_items = [item for item in state.outbox
                  if item.status == "sent" and dates.get(item.snapshot_id) == candidate.ranking_date]
    sent_for_date = bool(sent_items)
    last_sent = max(sent_items, key=lambda item: (item.sent_at, item.created_at, item.id)) if sent_items else None
    delivered_snapshot = next((item for item in rankings.snapshots if last_sent and item.id == last_sent.snapshot_id), None)
    changed_since_delivery = delivered_snapshot is not None and not _same_sporting_content(delivered_snapshot, observation)

    outbox = list(state.outbox)
    if snapshot_status == "revised" and any(
        item.status == "pending" and not _sendable(item) and item.superseded_by is None
        and dates.get(item.snapshot_id) == candidate.ranking_date for item in outbox
    ):
        # A new event must not bypass an unresolved delivery of this edition.
        raise RankingSourceError("ranking_source_schema_changed")

    # Every new publication produces one digest, changed or not; a revision of
    # an already-delivered publication is only worth a message when it changes
    # the sporting facts.
    event_type: str | None = None
    if sent_for_date:
        pending_for_date = any(item.status == "pending" and item.retryable
                               and dates.get(item.snapshot_id) == candidate.ranking_date for item in outbox)
        # A pending correction for B must be superseded when the source
        # returns to already-delivered A. Otherwise B could still be sent.
        event_type = "ranking_correction" if changed_since_delivery or pending_for_date else None
    else:
        event_type = "weekly_digest"

    if event_type is not None:
        item_id = event_id(candidate.id, event_type)
        if snapshot_status == "revised":
            outbox = [replace(item, retryable=False, superseded_by=item_id)
                      if item.status == "pending" and item.retryable and dates.get(item.snapshot_id) == candidate.ranking_date
                      else item for item in outbox]
        if not any(item.id == item_id for item in outbox):
            outbox.append(
                OutboxItem(
                    id=item_id,
                    snapshot_id=candidate.id,
                    event_type=event_type,
                    status="pending",
                    attempts=0,
                    created_at=captured_at,
                    sent_at=None,
                    provider="callmebot",
                    last_error_code=None,
                )
            )

    updated_state = _sort_outbox(replace(state, outbox=tuple(outbox)), updated_rankings)
    return CollectionOutcome(
        snapshot_status=snapshot_status,
        outbox_status="created" if event_type is not None else "none",
        rankings=updated_rankings,
        state=updated_state,
        snapshot=candidate,
        delta=delta,
    )


def collect(
    *,
    source: RankingSource,
    rankings_path: Path = DEFAULT_RANKINGS_PATH,
    state_path: Path = DEFAULT_STATE_PATH,
    baseline_path: Path = DEFAULT_BASELINE_PATH,
    captured_at: str | None = None,
    clock: Callable[[], datetime] = utc_now,
    calendar: EditionCalendar | None = None,
    incidents_path: Path | None = None,
) -> CollectionOutcome:
    recover_collection(rankings_path, state_path, incidents_path)
    rankings = load_rankings(rankings_path)
    observation, freshness = _freshness_checked_observation(
        source, rankings, baseline_path=baseline_path, now=clock(), calendar=calendar
    )
    state = load_alert_state(state_path, rankings)
    try:
        outcome = plan_collection(rankings, state, observation, captured_at=captured_at or freshness.checked_at)
    except RankingSourceError as exc:
        exc.freshness = replace(freshness, state=FreshnessState.SOURCE_ERROR, reason=exc.code)
        raise
    outcome = replace(outcome, freshness=freshness,
                      source_telemetry=safe_source_telemetry(getattr(source, "last_telemetry", None)))
    ledger = load_incidents(incidents_path) if incidents_path is not None else None
    recovered = plan_recovery(ledger, ranking_date=outcome.snapshot.ranking_date, now=freshness.checked_at) if ledger is not None else None
    if outcome.snapshot_status != "unchanged" or recovered != ledger:
        save_collection(rankings_path, state_path, rankings=outcome.rankings, state=outcome.state,
                        incidents_path=incidents_path if recovered != ledger else None,
                        incidents=recovered)
    return outcome


def _message_for_snapshot(rankings: RankingsData, snapshot: RankingSnapshot, event_type: str) -> str:
    previous = _previous_date_snapshot(rankings.snapshots, snapshot.ranking_date)
    history = tuple(item for item in rankings.snapshots if item.ranking_date < snapshot.ranking_date)
    delta = compare_snapshots(previous, snapshot, history) if previous is not None else None
    return format_message(snapshot, delta, correction=event_type == "ranking_correction")


def deliver(
    *,
    provider: NotificationProvider,
    rankings_path: Path = DEFAULT_RANKINGS_PATH,
    state_path: Path = DEFAULT_STATE_PATH,
    now: Callable[[], str] = _utc_now,
    checkpoint: Callable[[], None] | None = None,
    edition_date: str | None = None,
    validate_edition: Callable[[], None] | None = None,
) -> int:
    if provider.name != "callmebot":
        raise ConfigurationError("invalid_delivery_provider")
    rankings = load_rankings(rankings_path)
    state = load_alert_state(state_path, rankings)
    latest_date = max((snapshot.ranking_date for snapshot in rankings.snapshots), default=None)
    selected_date = edition_date or latest_date
    if selected_date != latest_date:
        raise ConfigurationError("ranking_delivery_edition_mismatch")
    sent_count = 0
    for item in state.outbox:
        if not _sendable(item):
            continue
        snapshot = next((value for value in rankings.snapshots if value.id == item.snapshot_id), None)
        if snapshot is None:
            raise StorageError("invalid_snapshot_reference")
        if snapshot.ranking_date != selected_date:
            # Keep older intentions and their receipts intact for reconciliation.
            continue
        if validate_edition is not None:
            validate_edition()
        # Reserve locally and remotely before the irreversible provider call.
        # A crash leaves an uncertain, non-retryable record with a unique nonce.
        reserved = replace(item, attempts=item.attempts + 1, retryable=False,
                           last_error_code="provider_outcome_unknown", attempt_id=uuid4().hex)
        state = replace(state, outbox=tuple(reserved if value.id == item.id else value for value in state.outbox))
        save_alert_state(state_path, state, rankings)
        if checkpoint is not None:
            checkpoint()
        if validate_edition is not None:
            # A slow durable push can cross the calendar's local-day boundary.
            # If it does, retain the claim without making a provider request.
            validate_edition()
        try:
            receipt = provider.send(
                message=_message_for_snapshot(rankings, snapshot, item.event_type), event_id=item.id
            )
            if receipt.provider != "callmebot" or receipt.delivery_status != "provider_accepted":
                raise DeliveryError("provider_response_ambiguous", max(1, getattr(provider, "last_attempt_count", 1)))
        except DeliveryError as exc:
            failed = replace(
                reserved,
                attempts=item.attempts + max(1, exc.attempts),
                last_error_code=exc.code,
                retryable=exc.retryable and exc.code == "http_429",
            )
            state = replace(state, outbox=tuple(failed if value.id == item.id else value for value in state.outbox))
            save_alert_state(state_path, state, rankings)
            if checkpoint is not None:
                checkpoint()
            raise
        attempt_count = max(1, int(getattr(provider, "last_attempt_count", 1)))
        delivered = replace(
            reserved,
            status="sent",
            attempts=item.attempts + attempt_count,
            sent_at=receipt.accepted_at or now(),
            last_error_code=None,
            retryable=False,
            delivery_status="provider_accepted",
        )
        state = replace(state, outbox=tuple(delivered if value.id == item.id else value for value in state.outbox))
        save_alert_state(state_path, state, rankings)
        if checkpoint is not None:
            checkpoint()
        sent_count += 1
    return sent_count


def dry_run(
    *,
    source: RankingSource,
    rankings_path: Path = DEFAULT_RANKINGS_PATH,
    state_path: Path = DEFAULT_STATE_PATH,
    baseline_path: Path = DEFAULT_BASELINE_PATH,
    captured_at: str | None = None,
    clock: Callable[[], datetime] = utc_now,
    calendar: EditionCalendar | None = None,
) -> CollectionOutcome:
    rankings = load_rankings(rankings_path)
    observation, freshness = _freshness_checked_observation(
        source, rankings, baseline_path=baseline_path, now=clock(), calendar=calendar
    )
    state = load_alert_state(state_path, rankings)
    try:
        outcome = plan_collection(rankings, state, observation, captured_at=captured_at or freshness.checked_at)
    except RankingSourceError as exc:
        exc.freshness = replace(freshness, state=FreshnessState.SOURCE_ERROR, reason=exc.code)
        raise
    return replace(outcome, freshness=freshness,
                   source_telemetry=safe_source_telemetry(getattr(source, "last_telemetry", None)))


def _freshness_checked_observation(
    source: RankingSource,
    rankings: RankingsData,
    *,
    baseline_path: Path,
    now: datetime,
    calendar: EditionCalendar | None,
) -> tuple[RankingObservation, FreshnessAssessment]:
    """Only validated observations may reach sporting persistence.

    PENDING may catch up an observed prior edition within the current grace
    period; it never confirms the expected edition or authorizes its delivery.

    Errors carry a structured assessment for operational incident handling.
    An incident can be persisted separately without making a stale snapshot.
    Historical backfill should use explicit verified observations and
    ``plan_collection`` rather than bypass this live-source gate silently.
    """
    last_date = max((snapshot.ranking_date for snapshot in rankings.snapshots), default=None)
    def assess(value):
        if calendar is not None:
            return assess_publication(value, now=now, calendar=calendar, last_valid_date=last_date)
        return assess_observation(value, now=now, last_valid_date=last_date)
    try:
        observation = _observation_from_source(source, rankings, baseline_path=baseline_path)
    except (RankingSourceError, DomainValidationError, AtpSourceError, TimeoutError) as exc:
        if not isinstance(exc, RankingSourceError):
            code = ("ranking_source_identity_mismatch" if getattr(exc, "code", None) == "atp_identity_mismatch"
                    else "ranking_source_timeout" if isinstance(exc, TimeoutError)
                    else "ranking_source_schema_changed")
            exc = RankingSourceError(code)
        telemetry = getattr(source, "last_telemetry", None)
        actual_date = telemetry.get("source_ranking_date") if isinstance(telemetry, dict) else None
        assessment = assess(actual_date)
        # A response older than already-persisted facts is a source regression,
        # not evidence that the current edition missed its publication SLA.
        assessment = replace(assessment, state=FreshnessState.SOURCE_ERROR, reason=exc.code)
        exc.freshness = assessment
        raise exc from None
    assessment = assess(observation.ranking_date)
    if assessment.state in {FreshnessState.STALE, FreshnessState.SOURCE_ERROR}:
        error = RankingSourceError(assessment.reason or "ranking_source_stale")
        error.freshness = assessment
        raise error
    return observation, assessment


def _observation_from_source(
    source: RankingSource,
    rankings: RankingsData,
    *,
    baseline_path: Path,
) -> RankingObservation:
    try:
        value = source.fetch()
    except (RankingSourceError, DomainValidationError, AtpSourceError, TimeoutError):
        raise
    except Exception:
        # Browser/HTTP adapter exceptions may carry URLs, cookies or bodies.
        raise RankingSourceError("ranking_source_incomplete") from None
    if isinstance(value, RankingObservation):
        if getattr(source, "name", value.source) != value.source:
            raise RankingSourceError("ranking_source_identity_mismatch")
        if rankings.snapshots and value.ranking_date < max(item.ranking_date for item in rankings.snapshots):
            raise RankingSourceError("ranking_source_stale")
        return value
    if not isinstance(value, RawRankingObservation):
        raise DomainValidationError("atp_incomplete_observation")

    if getattr(source, "name", None) != value.source:
        raise RankingSourceError("ranking_source_identity_mismatch")
    observation = RankingObservation(
        atp_id=value.atp_id,
        name=value.name,
        ranking_date=value.ranking_date,
        source=value.source,
        singles=DisciplineRanking(rank=value.singles.rank, points=value.singles.points),
        doubles=DisciplineRanking(rank=value.doubles.rank, points=value.doubles.points),
    )
    if rankings.snapshots and observation.ranking_date < rankings.snapshots[-1].ranking_date:
        raise RankingSourceError("ranking_source_stale")

    history = tuple(
        snapshot for snapshot in rankings.snapshots if snapshot.ranking_date <= observation.ranking_date
    )
    return enrich_with_baseline(observation, history=history, baseline_path=baseline_path)



class _FixtureSource:
    def __init__(self, path: str):
        self.path = path

    def fetch(self) -> RankingObservation:
        return load_fixture(self.path)


def _paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--rankings-path", type=Path, default=DEFAULT_RANKINGS_PATH, help=argparse.SUPPRESS)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH, help=argparse.SUPPRESS)
    parser.add_argument("--incidents-path", type=Path, default=DEFAULT_INCIDENTS_PATH, help=argparse.SUPPRESS)


SOURCE_CHOICES = ("itf",)


def _source_argument(parser: argparse.ArgumentParser, *, allow_fixture: bool = False) -> None:
    parser.add_argument("--calendar-path", type=Path, default=None,
                        help="explicit legacy calendar assessment; omitted in autonomous operation")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", choices=SOURCE_CHOICES)
    if allow_fixture:
        group.add_argument("--fixture")


def _selected_source(name: str) -> RankingSource:
    if name == "itf":
        from ranking_alerts.itf_source import ItfRankingSource

        return ItfRankingSource()
    raise DomainValidationError("invalid_source")


def _sendable(item: OutboxItem) -> bool:
    # Legacy retryable timeouts/5xx did not prove non-acceptance either.
    return item.status == "pending" and item.retryable and item.last_error_code in {None, "http_429"}


def has_pending_outbox(*, rankings_path: Path, state_path: Path) -> bool:
    rankings = load_rankings(rankings_path)
    state = load_alert_state(state_path, rankings)
    return any(_sendable(item) for item in state.outbox)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ATP ranking alert automation")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check-config", help="validate provider configuration")
    check.add_argument("--provider", choices=("callmebot",), required=True)

    collect_parser = commands.add_parser("collect", help="collect and persist an ATP snapshot")
    _paths(collect_parser)
    _source_argument(collect_parser)

    deliver_parser = commands.add_parser("deliver", help="deliver pending outbox items")
    deliver_parser.add_argument("--provider", choices=("callmebot",), required=True)
    deliver_parser.add_argument("--durable-git", action="store_true", help="publish each reservation before sending; required for delivery")
    deliver_parser.add_argument("--incidents-only", action="store_true", help="block sporting delivery when collection did not confirm a fresh edition")
    deliver_parser.add_argument("--edition-date", help="edition confirmed by the successful FRESH collection; required for sporting delivery")
    _paths(deliver_parser)

    checkpoint_parser = commands.add_parser("checkpoint", help="recover and publish the complete ranking state bundle")
    _paths(checkpoint_parser)

    dry_parser = commands.add_parser("dry-run", help="collect and render without side effects")
    _source_argument(dry_parser, allow_fixture=True)
    _paths(dry_parser)

    telemetry_parser = commands.add_parser("telemetry", help="summarize workflow scheduling without changing state")
    telemetry_parser.add_argument("--event-name", choices=("schedule", "workflow_dispatch"), required=True)
    telemetry_parser.add_argument("--run-metadata", type=Path, required=True)
    _paths(telemetry_parser)
    return parser


def _print_outcome(outcome: CollectionOutcome, *, show_message: bool) -> None:
    if outcome.freshness:
        report = outcome.freshness
        print(f"freshness={report.state.value} expected_date={report.expected_date} actual_date={report.actual_date} cutoff={report.cutoff} source_age_days={report.source_age_days}")
    print(f"snapshot={outcome.snapshot_status} outbox={outcome.outbox_status}")
    if not show_message:
        return
    if outcome.outbox_status == "created":
        item = next(item for item in outcome.state.outbox if item.snapshot_id == outcome.snapshot.id)
        print(_message_for_snapshot(outcome.rankings, outcome.snapshot, item.event_type))
    else:
        print("message=none (no new publication)")


def _git_checkpoint(args: argparse.Namespace) -> GitCheckpoint:
    root = Path.cwd().resolve()
    requested = (args.rankings_path, args.state_path, args.incidents_path)
    if tuple(path.resolve() for path in requested) != tuple(root / path for path in STATE_PATHS[:3]):
        raise ConfigurationError("checkpoint_requires_canonical_paths")
    return GitCheckpoint(root)


def main(argv: Sequence[str] | None = None, *, clock: Callable[[], datetime] = utc_now,
         checkpoint: Callable[[], None] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with state_lock(args.state_path) if args.command in {"collect", "deliver", "checkpoint"} else nullcontext():
            if args.command in {"collect", "deliver", "checkpoint"}:
                recover_collection(args.rankings_path, args.state_path, args.incidents_path)
            return _main(args, clock=clock, checkpoint=checkpoint)
    except StorageError as exc:
        print(f"error={exc.code}", file=sys.stderr)
        return 1


def _main(args: argparse.Namespace, *, clock: Callable[[], datetime], checkpoint: Callable[[], None] | None) -> int:
    source = None
    assessment = None
    error_code = None
    try:
        if args.command == "checkpoint":
            _git_checkpoint(args)()
            print("ranking_state=checkpointed")
            return 0
        if args.command == "telemetry":
            metadata = json.loads(args.run_metadata.read_text(encoding="utf-8"))
            report = schedule_timing(
                event=args.event_name,
                created_at=datetime.fromisoformat(metadata["created_at"].replace("Z", "+00:00")),
                started_at=datetime.fromisoformat(metadata["run_started_at"].replace("Z", "+00:00")),
            )
            rankings = load_rankings(args.rankings_path)
            last_date = max((snapshot.ranking_date for snapshot in rankings.snapshots), default=None)
            source_age = (datetime.fromisoformat(report.started_at.replace("Z", "+00:00")).date() - datetime.fromisoformat(last_date).date()).days if last_date else None
            emit_schedule_summary(report, source_age_days=source_age)
            return 0
        if args.command == "check-config":
            import os

            validate_callmebot_config(os.environ.get("CALLMEBOT_PHONE"), os.environ.get("CALLMEBOT_API_KEY"))
            print("provider=callmebot config=valid")
            return 0
        if args.command == "collect":
            ledger = load_incidents(args.incidents_path)
            source = _selected_source(args.source)
            outcome = collect(
                source=source,
                rankings_path=args.rankings_path,
                state_path=args.state_path,
                calendar=load_calendar(args.calendar_path) if args.calendar_path is not None else None,
                clock=clock,
                incidents_path=args.incidents_path,
            )
            assessment = outcome.freshness
            recovered = load_incidents(args.incidents_path)
            print(f"incident_recovery={len(recovered.events) - len(ledger.events)}")
            _print_outcome(outcome, show_message=False)
            return 0
        if args.command == "deliver":
            ledger = load_incidents(args.incidents_path)
            sporting_error = None
            sporting_review = 0
            validate_edition = None
            try:
                rankings = load_rankings(args.rankings_path)
                state = load_alert_state(args.state_path, rankings)
                dates = _snapshot_date_by_id(rankings)
                sporting_pending = False
                sporting_review = sum(item.status == "pending" and item.superseded_by is None and not _sendable(item) for item in state.outbox)
                if not args.incidents_only and any(_sendable(item) for item in state.outbox):
                    if not args.edition_date:
                        raise ConfigurationError("ranking_delivery_edition_required")
                    calendar = load_calendar()
                    latest_date = max(dates.values(), default=None)
                    def validate_edition():
                        report = assess_publication(args.edition_date, now=clock(), calendar=calendar)
                        if report.state != FreshnessState.FRESH or args.edition_date != latest_date:
                            raise ConfigurationError("ranking_delivery_edition_not_fresh")
                    validate_edition()
                    sporting_pending = any(_sendable(item) and dates[item.snapshot_id] == args.edition_date for item in state.outbox)
                    held = sum(_sendable(item) and dates[item.snapshot_id] != args.edition_date for item in state.outbox)
                    sporting_review += held
                    if held:
                        print(f"sporting_edition_held={held}")
            except (StorageError, CalendarError, ConfigurationError) as exc:
                sporting_error = exc
                sporting_pending = False
            incident_review = len(unresolved_deliveries(ledger))
            needs_review = sporting_review + incident_review
            if needs_review:
                print(f"delivery_review_required={needs_review}")
                append_summary(f"### ATP ranking — delivery review\n\n{needs_review} unresolved provider attempts or older sporting intentions require operator reconciliation; automatic replay is disabled for these records.")
            if not sporting_pending and not pending_incidents(ledger):
                if sporting_error is not None:
                    raise sporting_error
                if needs_review:
                    raise ConfigurationError("ranking_delivery_review_required")
                # Provider credentials are only required when there is work to send.
                print("provider=callmebot provider_accepted=0")
                return 0
            import os
            if os.environ.get("ATP_RANKING_DELIVERY_ENABLED") != "true":
                raise ConfigurationError("ranking_delivery_disabled")
            if args.durable_git:
                checkpoint = _git_checkpoint(args)
            elif checkpoint is None:
                raise ConfigurationError("ranking_checkpoint_required")
            # A retry inside send() can cross a local edition/validity boundary.
            # Persist a definite 429 rejection, then revalidate and reserve in
            # a later CLI run instead of issuing another unchecked request.
            provider = CallMeBotProvider.from_env(max_attempts=1)
            count = 0
            if sporting_pending:
                try:
                    count = deliver(provider=provider, rankings_path=args.rankings_path, state_path=args.state_path,
                                    checkpoint=checkpoint, edition_date=args.edition_date,
                                    validate_edition=validate_edition)
                except DeliveryError as exc:
                    sporting_error = exc
            # Operational incidents use their own ledger and remain actionable
            # when sporting persistence or the sporting provider attempt fails.
            count += deliver_incidents(provider=provider, path=args.incidents_path,
                                       now=clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                                       checkpoint=checkpoint)
            print(f"provider=callmebot provider_accepted={count}")
            if sporting_error is not None:
                raise sporting_error
            if needs_review:
                raise ConfigurationError("ranking_delivery_review_required")
            return 0
        source: RankingSource = (
            _FixtureSource(args.fixture) if args.fixture else _selected_source(args.source)
        )
        ledger = load_incidents(args.incidents_path)
        outcome = dry_run(
            source=source,
            rankings_path=args.rankings_path,
            state_path=args.state_path,
            calendar=load_calendar(args.calendar_path) if args.calendar_path is not None else None,
            clock=clock,
        )
        assessment = outcome.freshness
        recovered = plan_recovery(ledger, ranking_date=outcome.snapshot.ranking_date, now=assessment.checked_at)
        print(f"incident_recovery_would_resolve={len(recovered.events) - len(ledger.events)}")
        _print_outcome(outcome, show_message=True)
        return 0
    except (
        AtpSourceError,
        CareerHighBaselineError,
        CalendarError,
        ConfigurationError,
        DeliveryError,
        DomainValidationError,
        RankingSourceError,
        StorageError,
    ) as exc:
        error_code = exc.code
        assessment = getattr(exc, "freshness", None)
        if assessment:
            print(f"freshness={assessment.state.value} expected_date={assessment.expected_date} actual_date={assessment.actual_date} cutoff={assessment.cutoff} source_age_days={assessment.source_age_days}")
        if assessment and assessment.state in {FreshnessState.STALE, FreshnessState.SOURCE_ERROR} and args.command in {"collect", "dry-run"}:
            try:
                ledger = load_incidents(args.incidents_path)
                details = dict(expected_date=assessment.expected_date,
                               last_valid_date=assessment.last_valid_date,
                               source=getattr(source, "name", "itf"),
                               cutoff_at=assessment.cutoff, now=assessment.checked_at)
                if assessment.state == FreshnessState.STALE:
                    details["last_valid_date"] = assessment.actual_date or assessment.last_valid_date
                    new_ledger = plan_stale(ledger, **details)
                else:
                    new_ledger = plan_source_error(ledger, **details, error_code=assessment.reason,
                                                   telemetry=getattr(source, "last_telemetry", None))
                created = new_ledger != ledger
                if args.command == "collect" and created:
                    save_incidents(args.incidents_path, new_ledger)
                print(f"snapshot=blocked outbox=none incident={'would_create' if args.command == 'dry-run' and created else 'created' if created else 'unchanged'}")
                if args.command == "dry-run" and created:
                    print(format_incident(new_ledger.events[-1]))
                if assessment.state == FreshnessState.SOURCE_ERROR:
                    print(f"error={exc.code}", file=sys.stderr)
                    return 1
                return 0
            except StorageError as ledger_error:
                error_code = ledger_error.code
                print(f"error={ledger_error.code}", file=sys.stderr)
                return 1
        print(f"error={exc.code}", file=sys.stderr)
        return 1
    except Exception:
        error_code = "unexpected_failure"
        print("error=unexpected_failure", file=sys.stderr)
        return 1
    finally:
        if args.command in {"collect", "dry-run"}:
            try:
                emit_collection_summary(assessment, source_telemetry=getattr(source, "last_telemetry", None), error_code=error_code)
                if args.command == "collect":
                    import os
                    if os.environ.get("GITHUB_OUTPUT"):
                        allowed = error_code is None and assessment is not None and assessment.state == FreshnessState.FRESH
                        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
                            output.write(f"sporting_delivery_allowed={'true' if allowed else 'false'}\n")
                            output.write(f"sporting_edition_date={assessment.actual_date if allowed else ''}\n")
            except OSError:
                print("telemetry=summary_unavailable", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
