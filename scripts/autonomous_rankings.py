#!/usr/bin/env python3
"""Publication-driven ATP runtime; production requires initial release configuration."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import update_rankings as legacy
from ranking_alerts.durability import GitCheckpoint, state_lock
from ranking_alerts.providers import CallMeBotProvider, ConfigurationError
from ranking_alerts.runtime_state import DEFAULT_RUNTIME_PATH, append_cycle
from ranking_alerts.storage import StorageError, load_alert_state, load_rankings
from ranking_alerts.telemetry import safe_source_telemetry

DEFAULT_DELIVERY_PATH = Path("automation/state/ranking_delivery.json")


def run_cycle(*, source, root: Path, now: Callable[[], datetime], dry: bool = False,
              checkpoint=None, provider_factory=None, ops_alert=None) -> dict:
    """Caller serializes the entire cycle; dependency injection is for isolated tests."""
    from ranking_alerts.autonomous_delivery import (
        load_delivery, save_delivery, plan_digest, plan_weekly_status,
        plan_operational, plan_provider_health, deliver_autonomously,
    )
    from ranking_alerts.autonomous_scheduler import weekly_period

    instant = now().astimezone(timezone.utc)
    stamp = instant.isoformat().replace("+00:00", "Z")
    rankings_path = root / legacy.DEFAULT_RANKINGS_PATH
    state_path = root / legacy.DEFAULT_STATE_PATH
    incidents_path = root / legacy.DEFAULT_INCIDENTS_PATH
    delivery_path = root / DEFAULT_DELIVERY_PATH
    error = None
    outcome = None
    last_date = None
    try:
        action = legacy.dry_run if dry else legacy.collect
        kwargs = dict(source=source, rankings_path=rankings_path, state_path=state_path,
                      baseline_path=root / legacy.DEFAULT_BASELINE_PATH, clock=lambda: instant)
        if not dry:
            kwargs["incidents_path"] = incidents_path
        outcome = action(**kwargs)
        last_date = max((s.ranking_date for s in outcome.rankings.snapshots), default=None)
        status = outcome.freshness.state.value
    except Exception as exc:
        # Never retain browser/provider exception strings, which can contain secrets.
        error = getattr(exc, "code", "ranking_source_incomplete")
        import re
        if not isinstance(error, str) or not re.fullmatch(r"[a-z0-9_]+", error):
            error = "ranking_source_incomplete"
        status = "SOURCE_ERROR"
        try:
            last_date = max((s.ranking_date for s in load_rankings(rankings_path).snapshots), default=None)
        except StorageError:
            pass
    result = {"collection": status, "last_valid_date": last_date, "error_code": error}
    if dry:
        result["writes"] = False
        result["provider_requests"] = 0
        return result

    if checkpoint is None:
        raise ConfigurationError("ranking_checkpoint_required")
    if provider_factory is None:
        provider_factory = lambda: CallMeBotProvider.from_env(max_attempts=1)
    try:
        provider = provider_factory()
        result["provider_configuration"] = "configured"
    except ConfigurationError:
        provider = None
        result["provider_configuration"] = "unavailable"
    _, episode = append_cycle(root / DEFAULT_RUNTIME_PATH, at=stamp, state=status,
                              last_valid_date=last_date, error_code=error,
                              provenance=safe_source_telemetry(getattr(source, "last_telemetry", None)))
    ledger = load_delivery(delivery_path)
    if outcome:
        # Replanning all observed editions recovers a crash after sporting commit.
        # The delivery ledger handles old receipts, staleness and per-edition identity.
        state = load_alert_state(state_path, outcome.rankings)
        latest = {}
        for snapshot in sorted(outcome.rankings.snapshots, key=legacy.snapshot_sort_key):
            latest[snapshot.ranking_date] = snapshot
        for snapshot in latest.values():
            ledger = plan_digest(ledger, snapshot_id=snapshot.id, ranking_date=snapshot.ranking_date,
                                 message=legacy._message_for_snapshot(outcome.rankings, snapshot, "weekly_digest"),
                                 now=stamp, legacy_state=state, legacy_rankings=outcome.rankings)
    if episode:
        message = (f"ATP monitor {status}; data date: {last_date or 'unknown'}; checked: {stamp}; "
                   f"code: {error or 'source_recovered'}")
        ledger = plan_operational(ledger, event_id=episode, message=message, now=stamp)
    ledger = plan_weekly_status(ledger, period=weekly_period(instant), last_verified_date=last_date,
                                checked_at=stamp, now=stamp, status=status)
    ledger = plan_provider_health(ledger, configured=provider is not None,
                                  last_verified_date=last_date, now=stamp)
    save_delivery(delivery_path, ledger)
    checkpoint()
    report = deliver_autonomously(path=delivery_path, provider=provider,
                                  checkpoint=checkpoint,
                                  now=lambda: now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                                  ops_alert=ops_alert, allow_editions=outcome is not None)
    from dataclasses import asdict
    result["notification"] = asdict(report)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run",))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = Path.cwd().resolve()
        if not args.dry_run and os.environ.get("ATP_RANKING_DELIVERY_ENABLED") != "true":
            raise ConfigurationError("ranking_delivery_disabled")
        checkpoint = None if args.dry_run else GitCheckpoint(root)
        from ranking_alerts.itf_source import ItfRankingSource
        from ranking_alerts.autonomous_scheduler import send_operational_alert
        from contextlib import nullcontext
        with nullcontext() if args.dry_run else state_lock(root / legacy.DEFAULT_STATE_PATH):
            result = run_cycle(source=ItfRankingSource(), root=root,
                               now=lambda: datetime.now(timezone.utc), dry=args.dry_run,
                               checkpoint=checkpoint, ops_alert=send_operational_alert)
        import json
        print("autonomous_cycle=" + json.dumps(result, sort_keys=True))
        return 1 if result["error_code"] or result.get("provider_configuration") == "unavailable" else 0
    except Exception as exc:
        code = getattr(exc, "code", "autonomous_runtime_failed")
        print(f"error={code if isinstance(exc, (StorageError, ConfigurationError)) else 'autonomous_runtime_failed'}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
