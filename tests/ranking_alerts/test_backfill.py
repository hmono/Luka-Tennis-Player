from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.ranking_alerts.backfill import backfill
from scripts.ranking_alerts.domain import (
    DisciplineRanking, DomainValidationError, RankingObservation, RankingsData, build_snapshot,
)
from scripts.ranking_alerts.source import RawDisciplineRanking, RawRankingObservation, RankingSourceError
from scripts.ranking_alerts.storage import load_rankings, save_rankings


class Source:
    name = "itf"

    def __init__(self, edition="2026-10-05", singles=2250):
        self.edition, self.singles = edition, singles

    def fetch(self):
        return RawRankingObservation(source="itf", atp_id="B0UF", name="Luka Bojicic Ono",
            ranking_date=self.edition,
            singles=RawDisciplineRanking(status="ranked", rank=self.singles, points=None),
            doubles=RawDisciplineRanking(status="ranked", rank=1417, points=None))


class BackfillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "rankings.json"
        self.state = self.root / "state.json"
        baseline = RankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
            ranking_date="2026-09-28", singles=DisciplineRanking(rank=2237, points=None),
            doubles=DisciplineRanking(rank=1401, points=None))
        save_rankings(self.path, RankingsData(snapshots=(build_snapshot(baseline, "2026-09-29T12:00:00Z"),)))
        self.state.write_text('{"schema_version":1,"outbox":[]}\n')
        self.original = self.path.read_bytes()
        self.state_original = self.state.read_bytes()

    def run_backfill(self, source=Source(), **kwargs):
        return backfill(source=source, as_of="2026-10-05", rankings_path=self.path,
                        state_path=self.state, captured_at="2026-10-12T21:00:00Z", **kwargs)

    def test_default_is_read_only_and_creates_no_alert_intent(self):
        result = self.run_backfill()
        self.assertEqual("would_create", result.status)
        self.assertEqual(self.original, self.path.read_bytes())
        self.assertEqual(self.state_original, self.state.read_bytes())

    def test_apply_appends_verified_edition_and_rerun_preserves_every_byte(self):
        result = self.run_backfill(apply=True)
        self.assertEqual("created", result.status)
        self.assertEqual(load_rankings(self.path).snapshots[0], load_rankings_before(self.original).snapshots[0])
        stored = self.path.read_bytes()
        self.assertEqual("unchanged", self.run_backfill(apply=True).status)
        self.assertEqual(stored, self.path.read_bytes())
        self.assertEqual(self.state_original, self.state.read_bytes())
        self.assertEqual(["2026-09-28", "2026-10-05"], [s.ranking_date for s in load_rankings(self.path).snapshots])

    def test_unverified_edition_unqualified_source_or_revision_never_writes(self):
        with self.assertRaises(DomainValidationError):
            self.run_backfill(source=Source("2026-10-12"), apply=True)
        bad = Source()
        bad.name = "unqualified"
        with self.assertRaises(DomainValidationError):
            self.run_backfill(source=bad, apply=True)
        self.assertEqual(self.original, self.path.read_bytes())
        self.run_backfill(apply=True)
        stored = self.path.read_bytes()
        with self.assertRaises(DomainValidationError):
            self.run_backfill(source=Source(singles=2249), apply=True)
        self.assertEqual(stored, self.path.read_bytes())
        self.assertEqual(self.state_original, self.state.read_bytes())


def load_rankings_before(payload):
    import json
    from scripts.ranking_alerts.domain import rankings_from_dict
    return rankings_from_dict(json.loads(payload))


if __name__ == "__main__":
    unittest.main()
