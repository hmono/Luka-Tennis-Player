#!/usr/bin/env python3
"""Collect ATP rankings and deliver durable WhatsApp alert intentions."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from ranking_alerts.atp_source import AtpRankingSource, AtpSourceError, RankingSource, load_fixture
from ranking_alerts.domain import (
    OutboxItem,
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


def plan_collection(
    rankings: RankingsData,
    state: RankingAlertState,
    observation: RankingObservation,
    *,
    captured_at: str,
) -> CollectionOutcome:
    same_date = [item for item in rankings.snapshots if item.ranking_date == observation.ranking_date]
    latest_same_date = max(same_date, key=snapshot_sort_key) if same_date else None
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
    if previous is None:
        return CollectionOutcome(
            snapshot_status=snapshot_status,
            outbox_status="none",
            rankings=updated_rankings,
            state=state,
            snapshot=candidate,
            delta=None,
        )

    history = tuple(item for item in rankings.snapshots if item.ranking_date < candidate.ranking_date)
    delta = compare_snapshots(previous, candidate, history)
    should_notify = delta.has_changes
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

    event_type: str | None = None
    if sent_for_date:
        event_type = "ranking_correction"
    elif should_notify:
        event_type = "ranking_change"

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
    captured_at: str | None = None,
) -> CollectionOutcome:
    rankings = load_rankings(rankings_path)
    state = load_alert_state(state_path, rankings)
    observation = source.fetch()
    outcome = plan_collection(rankings, state, observation, captured_at=captured_at or _utc_now())
    if outcome.snapshot_status != "unchanged":
        save_rankings(rankings_path, outcome.rankings)
        save_alert_state(state_path, outcome.state, outcome.rankings)
    return outcome


def _message_for_snapshot(rankings: RankingsData, snapshot: RankingSnapshot) -> str:
    previous = _previous_date_snapshot(rankings.snapshots, snapshot.ranking_date)
    if previous is None:
        raise StorageError("invalid_outbox_baseline")
    history = tuple(item for item in rankings.snapshots if item.ranking_date < snapshot.ranking_date)
    return format_message(snapshot, compare_snapshots(previous, snapshot, history))


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
            receipt = provider.send(message=_message_for_snapshot(rankings, snapshot), event_id=item.id)
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
    captured_at: str | None = None,
) -> CollectionOutcome:
    rankings = load_rankings(rankings_path)
    state = load_alert_state(state_path, rankings)
    return plan_collection(rankings, state, source.fetch(), captured_at=captured_at or _utc_now())


class _FixtureSource:
    def __init__(self, path: str):
        self.path = path

    def fetch(self) -> RankingObservation:
        return load_fixture(self.path)


def _paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--rankings-path", type=Path, default=DEFAULT_RANKINGS_PATH, help=argparse.SUPPRESS)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH, help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ATP ranking alert automation")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check-config", help="validate provider configuration")
    check.add_argument("--provider", choices=("callmebot",), required=True)

    collect_parser = commands.add_parser("collect", help="collect and persist an ATP snapshot")
    _paths(collect_parser)

    deliver_parser = commands.add_parser("deliver", help="deliver pending outbox items")
    deliver_parser.add_argument("--provider", choices=("callmebot",), required=True)
    _paths(deliver_parser)

    dry_parser = commands.add_parser("dry-run", help="collect and render without side effects")
    dry_parser.add_argument("--fixture")
    _paths(dry_parser)
    return parser


def _print_outcome(outcome: CollectionOutcome, *, show_message: bool) -> None:
    print(f"snapshot={outcome.snapshot_status} outbox={outcome.outbox_status}")
    if not show_message:
        return
    if outcome.delta is None:
        print("message=none (baseline or unchanged)")
    elif outcome.outbox_status == "created":
        print(format_message(outcome.snapshot, outcome.delta))
    else:
        print("message=none (no ranking change)")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check-config":
            import os

            validate_callmebot_config(os.environ.get("CALLMEBOT_PHONE"), os.environ.get("CALLMEBOT_API_KEY"))
            print("provider=callmebot config=valid")
            return 0
        if args.command == "collect":
            outcome = collect(
                source=AtpRankingSource(),
                rankings_path=args.rankings_path,
                state_path=args.state_path,
            )
            _print_outcome(outcome, show_message=False)
            return 0
        if args.command == "deliver":
            provider = CallMeBotProvider.from_env()
            count = deliver(
                provider=provider,
                rankings_path=args.rankings_path,
                state_path=args.state_path,
            )
            print(f"provider=callmebot delivered={count}")
            return 0
        source: RankingSource = _FixtureSource(args.fixture) if args.fixture else AtpRankingSource()
        outcome = dry_run(
            source=source,
            rankings_path=args.rankings_path,
            state_path=args.state_path,
        )
        _print_outcome(outcome, show_message=True)
        return 0
    except (AtpSourceError, ConfigurationError, DeliveryError, DomainValidationError, StorageError) as exc:
        print(f"error={exc.code}", file=sys.stderr)
        return 1
    except Exception:
        print("error=unexpected_failure", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
