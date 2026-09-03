from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import update_rankings
from ranking_alerts.domain import DisciplineRanking, RankingObservation
from ranking_alerts.providers import DeliveryError
from ranking_alerts.storage import load_alert_state, load_rankings


def observation(
    ranking_date: str,
    *,
    singles_rank: int = 2000,
    singles_points: int = 5,
    doubles_rank: int = 1900,
    doubles_points: int = 6,
) -> RankingObservation:
    return RankingObservation(
        atp_id="B0UF",
        name="Luka Bojicic Ono",
        ranking_date=ranking_date,
        singles=DisciplineRanking(
            rank=singles_rank,
            points=singles_points,
            career_high_rank=min(1800, singles_rank),
            career_high_date="2025-12-01",
        ),
        doubles=DisciplineRanking(
            rank=doubles_rank,
            points=doubles_points,
            career_high_rank=min(1700, doubles_rank),
            career_high_date="2025-07-28",
        ),
    )


class FakeSource:
    def __init__(self, value: RankingObservation):
        self.value = value

    def fetch(self) -> RankingObservation:
        return self.value


class FailingProvider:
    name = "callmebot"
    last_attempt_count = 4

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, *, message: str, event_id: str):
        self.messages.append((event_id, message))
        raise DeliveryError("http_500", 4)


class UpdateRankingsIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.rankings_path = root / "data" / "rankings.json"
        self.state_path = root / "automation" / "state" / "ranking_alerts.json"

    def collect(self, value: RankingObservation, captured_at: str):
        return update_rankings.collect(
            source=FakeSource(value),
            rankings_path=self.rankings_path,
            state_path=self.state_path,
            captured_at=captured_at,
        )

    def test_bootstrap_is_persisted_without_outbox(self) -> None:
        outcome = self.collect(observation("2026-09-01"), "2026-09-01T12:00:00Z")

        self.assertEqual("created", outcome.snapshot_status)
        self.assertEqual("none", outcome.outbox_status)
        self.assertEqual(1, len(load_rankings(self.rankings_path).snapshots))
        self.assertEqual((), load_alert_state(self.state_path, outcome.rankings).outbox)

    def test_identical_observation_is_idempotent(self) -> None:
        value = observation("2026-09-01")
        self.collect(value, "2026-09-01T12:00:00Z")
        outcome = self.collect(value, "2026-09-01T13:00:00Z")

        self.assertEqual("unchanged", outcome.snapshot_status)
        self.assertEqual(1, len(load_rankings(self.rankings_path).snapshots))

    def test_change_creates_one_aggregated_pending_item(self) -> None:
        self.collect(observation("2026-09-01"), "2026-09-01T12:00:00Z")
        outcome = self.collect(
            observation("2026-09-08", singles_rank=1990, singles_points=7),
            "2026-09-08T12:00:00Z",
        )

        self.assertEqual("created", outcome.outbox_status)
        self.assertEqual(1, len(outcome.state.outbox))
        self.assertEqual(outcome.snapshot.id, outcome.state.outbox[0].snapshot_id)

    def test_revision_supersedes_unsent_intent_for_same_date(self) -> None:
        self.collect(observation("2026-09-01"), "2026-09-01T12:00:00Z")
        first = self.collect(
            observation("2026-09-08", singles_rank=1990),
            "2026-09-08T12:00:00Z",
        )
        revised = self.collect(
            observation("2026-09-08", singles_rank=1985),
            "2026-09-08T13:00:00Z",
        )

        self.assertEqual("revised", revised.snapshot_status)
        self.assertEqual(1, len(revised.state.outbox))
        self.assertNotEqual(first.state.outbox[0].id, revised.state.outbox[0].id)
        self.assertEqual(revised.snapshot.id, revised.state.outbox[0].snapshot_id)

    def test_dry_run_does_not_create_or_change_files(self) -> None:
        outcome = update_rankings.dry_run(
            source=FakeSource(observation("2026-09-01")),
            rankings_path=self.rankings_path,
            state_path=self.state_path,
            captured_at="2026-09-01T12:00:00Z",
        )

        self.assertEqual("created", outcome.snapshot_status)
        self.assertFalse(self.rankings_path.exists())
        self.assertFalse(self.state_path.exists())

    def test_delivery_failure_is_persisted_and_stops_fifo(self) -> None:
        self.collect(observation("2026-09-01"), "2026-09-01T12:00:00Z")
        self.collect(observation("2026-09-08", singles_rank=1990), "2026-09-08T12:00:00Z")
        self.collect(observation("2026-09-15", singles_rank=1980), "2026-09-15T12:00:00Z")
        provider = FailingProvider()

        with self.assertRaises(DeliveryError):
            update_rankings.deliver(
                provider=provider,
                rankings_path=self.rankings_path,
                state_path=self.state_path,
            )

        rankings = load_rankings(self.rankings_path)
        state = load_alert_state(self.state_path, rankings)
        self.assertEqual(1, len(provider.messages))
        self.assertEqual(4, state.outbox[0].attempts)
        self.assertEqual("http_500", state.outbox[0].last_error_code)
        self.assertEqual("pending", state.outbox[1].status)


if __name__ == "__main__":
    unittest.main()
