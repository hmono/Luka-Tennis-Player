#!/usr/bin/env python3
"""Recover one source-confirmed ATP edition. Default is read-only; no sends."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ranking_alerts.backfill import backfill
from ranking_alerts.career_high import CareerHighBaselineError
from ranking_alerts.domain import DomainValidationError
from ranking_alerts.itf_source import ItfRankingSource
from ranking_alerts.source import RankingSourceError
from ranking_alerts.storage import StorageError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("itf",), required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--apply", action="store_true", help="append verified snapshot without enqueueing any notification")
    parser.add_argument("--rankings-path", type=Path, default=Path("data/rankings.json"))
    parser.add_argument("--state-path", type=Path, default=Path("automation/state/ranking_alerts.json"))
    args = parser.parse_args(argv)
    source = ItfRankingSource()
    try:
        outcome = backfill(source=source, as_of=args.as_of, rankings_path=args.rankings_path,
                           state_path=args.state_path, apply=args.apply,
                           captured_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        print(json.dumps({"backfill": outcome.status, "ranking_date": outcome.ranking_date,
                          "snapshot_id": outcome.snapshot_id, "notification": "none"}))
        return 0
    except (CareerHighBaselineError, DomainValidationError, RankingSourceError, StorageError) as exc:
        print(f"error={exc.code}", file=sys.stderr)
        return 1
    finally:
        print(json.dumps({"source_telemetry": getattr(source, "last_telemetry", {})}, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
