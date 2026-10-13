from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS)) if str(SCRIPTS) not in sys.path else None
import autonomous_rankings
from ranking_alerts.domain import RankingsData
from ranking_alerts.providers import DeliveryError, DeliveryReceipt
from ranking_alerts.source import RawRankingObservation, RawDisciplineRanking, RankingSourceError
from ranking_alerts.storage import save_rankings, load_rankings


class Source:
    name = "itf"
    edition = "2026-10-05"
    ranks = (2250, 1417)
    error = None

    def fetch(self):
        if self.error:
            raise RankingSourceError(self.error)
        return RawRankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
            ranking_date=self.edition,
            singles=RawDisciplineRanking(status="ranked", rank=self.ranks[0], points=None),
            doubles=RawDisciplineRanking(status="ranked", rank=self.ranks[1], points=None))


class Provider:
    name = "callmebot"
    last_attempt_count = 1

    def __init__(self, clock):
        self.messages, self.clock, self.error = [], clock, None

    def send(self, *, message, event_id):
        self.messages.append((message, event_id))
        if self.error:
            raise self.error
        return DeliveryReceipt(provider=self.name, accepted_at=self.clock().isoformat().replace("+00:00", "Z"), http_status=200)


class AutonomousRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "data").mkdir()
        (self.root / "automation/state").mkdir(parents=True)
        save_rankings(self.root / "data/rankings.json", RankingsData(snapshots=()))
        shutil.copyfile(SCRIPTS.parent / "data/ranking_career_high_baseline.json",
                        self.root / "data/ranking_career_high_baseline.json")
        self.instant = datetime(2026, 10, 13, 12, 17, tzinfo=timezone.utc)
        self.source = Source()
        self.provider = Provider(lambda: self.instant)
        self.checkpoints, self.alerts = [], []

    def run_cycle(self, dry=False, checkpoint=None):
        return autonomous_rankings.run_cycle(source=self.source, root=self.root,
            now=lambda: self.instant, dry=dry,
            checkpoint=checkpoint or (lambda: self.checkpoints.append(self.instant)),
            provider_factory=lambda: self.provider,
            ops_alert=lambda event, text: self.alerts.append((event, text)) or True)

    def test_eight_weeks_without_calendar_one_status_per_period(self):
        self.run_cycle()
        for day in range(1, 57):
            self.instant = datetime(2026, 10, 13, 12, 17, tzinfo=timezone.utc) + timedelta(days=day)
            report = self.run_cycle()
            self.assertEqual("NO_NEW_EDITION_OBSERVED", report["collection"])
            self.run_cycle()
        messages = self.provider.messages
        weekly = [event for _, event in messages if "weekly" in event or "status" in event]
        self.assertEqual(9, len(weekly))  # initial catch-up period plus eight boundaries
        self.assertEqual(len(messages), len({event for _, event in messages}))
        snapshots = load_rankings(self.root / "data/rankings.json").snapshots
        self.assertEqual(1, len(snapshots))
        self.assertIsNone(snapshots[0].singles.points)
        self.assertIsNone(snapshots[0].doubles.points)
        self.assertFalse((self.root / "config").exists())

    def test_delayed_editions_identical_and_changed_ranks(self):
        self.run_cycle()
        self.instant += timedelta(days=12)
        self.assertEqual("NO_NEW_EDITION_OBSERVED", self.run_cycle()["collection"])
        self.source.edition = "2026-10-12"
        self.assertEqual("FRESH", self.run_cycle()["collection"])
        self.run_cycle()
        self.source.edition = "2026-10-19"
        self.source.ranks = (1800, 1300)
        self.assertEqual("FRESH", self.run_cycle()["collection"])
        snapshots = load_rankings(self.root / "data/rankings.json").snapshots
        self.assertEqual(3, len(snapshots))
        self.assertTrue(any("career high" in text.lower() for text, _ in self.provider.messages))

    def test_source_error_recovers_without_sporting_mutation(self):
        self.run_cycle()
        before = (self.root / "data/rankings.json").read_bytes()
        self.source.error = "ranking_source_identity_mismatch"
        for _ in range(4):
            self.instant += timedelta(days=1)
            self.assertEqual("SOURCE_ERROR", self.run_cycle()["collection"])
        self.assertEqual(before, (self.root / "data/rankings.json").read_bytes())
        self.source.error = None
        self.instant += timedelta(days=1)
        self.assertEqual("NO_NEW_EDITION_OBSERVED", self.run_cycle()["collection"])
        self.assertEqual(before, (self.root / "data/rankings.json").read_bytes())
        ops = [key for _, key in self.provider.messages if "source-error" in key]
        self.assertEqual(1, len(ops))

    def test_dry_run_has_no_state_writes_or_requests(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertFalse(self.run_cycle(dry=True)["writes"])
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual([], self.provider.messages)
        self.assertEqual([], self.checkpoints)

    def test_interrupted_checkpoint_replans_without_duplicate_digest(self):
        def interrupted():
            raise RuntimeError("mock checkpoint interruption")
        with self.assertRaises(RuntimeError):
            self.run_cycle(checkpoint=interrupted)
        self.assertEqual([], self.provider.messages)
        self.run_cycle()
        self.run_cycle()
        self.assertEqual(len(self.provider.messages), len({event for _, event in self.provider.messages}))
        self.assertEqual(1, len(load_rankings(self.root / "data/rankings.json").snapshots))

    def test_ambiguous_send_never_replays_and_next_edition_proceeds(self):
        self.provider.error = DeliveryError("transport_timeout", 1)
        self.run_cycle()
        attempts = len(self.provider.messages)
        self.provider.error = None
        self.instant += timedelta(days=1)
        self.run_cycle()
        self.assertEqual(attempts, len(self.provider.messages))
        self.assertTrue(self.alerts)
        self.source.edition = "2026-10-12"
        self.run_cycle()
        self.assertGreater(len(self.provider.messages), attempts)


if __name__ == "__main__":
    unittest.main()
