#!/usr/bin/env python3
"""Collect ATP rankings and deliver durable WhatsApp alert intentions."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

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
    load_calendar,
    utc_now,
)
from ranking_alerts.telemetry import emit_collection_summary, emit_schedule_summary, schedule_timing
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
    )

    existing = next((item for item in rankings.snapshots if item.id == candidate.id), None)
    if existing is not None:
        return CollectionOutcome(
            snapshot_status="unchanged",
            outbox_status="none",
            rankings=rankings,
            state=state,
            snapshot=existing,
            delta=None,
        )

    snapshot_status = "revised" if latest_same_date is not None else "created"
    snapshots = tuple(sorted(rankings.snapshots + (candidate,), key=snapshot_sort_key))
    updated_rankings = replace(rankings, snapshots=snapshots)
    previous = _previous_date_snapshot(rankings.snapshots, candidate.ranking_date)
    history = tuple(item for item in rankings.snapshots if item.ranking_date < candidate.ranking_date)
    delta = compare_snapshots(previous, candidate, history) if previous is not None else None
    has_changes = delta is not None and delta.has_changes
    dates = _snapshot_date_by_id(rankings)
    sent_for_date = any(
        item.status == "sent" and dates.get(item.snapshot_id) == candidate.ranking_date
        for item in state.outbox
    )

    outbox = list(state.outbox)
    if snapshot_status == "revised" and not sent_for_date:
        # Supersede unsent intent for this ATP date. Historical snapshots remain.
        outbox = [
            item
            for item in outbox
            if not (item.status == "pending" and dates.get(item.snapshot_id) == candidate.ranking_date)
        ]

    # Every new publication produces one digest, changed or not; a revision of
    # an already-delivered publication is only worth a message when it changes
    # the sporting facts.
    event_type: str | None = None
    if sent_for_date:
        event_type = "ranking_correction" if has_changes else None
    else:
        event_type = "weekly_digest"

    if event_type is not None:
        item_id = event_id(candidate.id, event_type)
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
) -> CollectionOutcome:
    rankings = load_rankings(rankings_path)
    state = load_alert_state(state_path, rankings)
    observation, freshness = _freshness_checked_observation(
        source, rankings, baseline_path=baseline_path, now=clock(), calendar=calendar or load_calendar()
    )
    outcome = plan_collection(rankings, state, observation, captured_at=captured_at or freshness.checked_at)
    outcome = replace(outcome, freshness=freshness)
    if outcome.snapshot_status != "unchanged":
        save_rankings(rankings_path, outcome.rankings)
        save_alert_state(state_path, outcome.state, outcome.rankings)
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
) -> int:
    rankings = load_rankings(rankings_path)
    state = load_alert_state(state_path, rankings)
    sent_count = 0
    for item in state.outbox:
        if item.status != "pending":
            continue
        snapshot = next((value for value in rankings.snapshots if value.id == item.snapshot_id), None)
        if snapshot is None:
            raise StorageError("invalid_snapshot_reference")
        try:
            receipt = provider.send(
                message=_message_for_snapshot(rankings, snapshot, item.event_type), event_id=item.id
            )
        except DeliveryError as exc:
            failed = replace(
                item,
                attempts=item.attempts + exc.attempts,
                last_error_code=exc.code,
            )
            state = replace(state, outbox=tuple(failed if value.id == item.id else value for value in state.outbox))
            save_alert_state(state_path, state, rankings)
            raise
        attempt_count = max(1, int(getattr(provider, "last_attempt_count", 1)))
        delivered = replace(
            item,
            status="sent",
            attempts=item.attempts + attempt_count,
            sent_at=receipt.accepted_at or now(),
            last_error_code=None,
        )
        state = replace(state, outbox=tuple(delivered if value.id == item.id else value for value in state.outbox))
        save_alert_state(state_path, state, rankings)
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
    state = load_alert_state(state_path, rankings)
    observation, freshness = _freshness_checked_observation(
        source, rankings, baseline_path=baseline_path, now=clock(), calendar=calendar or load_calendar()
    )
    return replace(
        plan_collection(rankings, state, observation, captured_at=captured_at or freshness.checked_at),
        freshness=freshness,
    )


def _freshness_checked_observation(
    source: RankingSource,
    rankings: RankingsData,
    *,
    baseline_path: Path,
    now: datetime,
    calendar: EditionCalendar,
) -> tuple[RankingObservation, FreshnessAssessment]:
    """Only validated current publications may reach sporting persistence.

    Errors carry a structured assessment for operational incident handling.
    An incident can be persisted separately without making a stale snapshot.
    Historical backfill should use explicit verified observations and
    ``plan_collection`` rather than bypass this live-source gate silently.
    """
    last_date = max((snapshot.ranking_date for snapshot in rankings.snapshots), default=None)
    try:
        observation = _observation_from_source(source, rankings, baseline_path=baseline_path)
    except RankingSourceError as exc:
        actual_date = getattr(source, "last_telemetry", {}).get("source_ranking_date")
        assessment = assess_publication(actual_date, now=now, calendar=calendar, last_valid_date=last_date)
        # A response older than already-persisted facts is a source regression,
        # not evidence that the current edition missed its publication SLA.
        assessment = replace(assessment, state=FreshnessState.SOURCE_ERROR, reason=exc.code)
        exc.freshness = assessment
        raise
    assessment = assess_publication(observation.ranking_date, now=now, calendar=calendar, last_valid_date=last_date)
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
    value = source.fetch()
    if isinstance(value, RankingObservation):
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


SOURCE_CHOICES = ("itf",)


def _source_argument(parser: argparse.ArgumentParser, *, allow_fixture: bool = False) -> None:
    parser.add_argument("--calendar-path", type=Path, default=DEFAULT_CALENDAR_PATH)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", choices=SOURCE_CHOICES)
    if allow_fixture:
        group.add_argument("--fixture")


def _selected_source(name: str) -> RankingSource:
    if name == "itf":
        from ranking_alerts.itf_source import ItfRankingSource

        return ItfRankingSource()
    raise DomainValidationError("invalid_source")


def has_pending_outbox(*, rankings_path: Path, state_path: Path) -> bool:
    rankings = load_rankings(rankings_path)
    state = load_alert_state(state_path, rankings)
    return any(item.status == "pending" for item in state.outbox)


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
    _paths(deliver_parser)

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
        print(format_message(outcome.snapshot, outcome.delta))
    else:
        print("message=none (no new publication)")


def main(argv: Sequence[str] | None = None, *, clock: Callable[[], datetime] = utc_now) -> int:
    args = build_parser().parse_args(argv)
    source = None
    assessment = None
    error_code = None
    try:
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
            source = _selected_source(args.source)
            outcome = collect(
                source=source,
                rankings_path=args.rankings_path,
                state_path=args.state_path,
                calendar=load_calendar(args.calendar_path),
                clock=clock,
            )
            assessment = outcome.freshness
            _print_outcome(outcome, show_message=False)
            return 0
        if args.command == "deliver":
            if not has_pending_outbox(rankings_path=args.rankings_path, state_path=args.state_path):
                # Provider credentials are only required when there is work to send.
                print("provider=callmebot delivered=0")
                return 0
            provider = CallMeBotProvider.from_env()
            count = deliver(
                provider=provider,
                rankings_path=args.rankings_path,
                state_path=args.state_path,
            )
            print(f"provider=callmebot delivered={count}")
            return 0
        source: RankingSource = (
            _FixtureSource(args.fixture) if args.fixture else _selected_source(args.source)
        )
        outcome = dry_run(
            source=source,
            rankings_path=args.rankings_path,
            state_path=args.state_path,
            calendar=load_calendar(args.calendar_path),
            clock=clock,
        )
        assessment = outcome.freshness
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
            except OSError:
                print("telemetry=summary_unavailable", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
