from __future__ import annotations

import sys
from contextlib import redirect_stderr
from dataclasses import replace
from io import StringIO
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import update_rankings
from ranking_alerts.domain import DisciplineRanking, RankingAlertState, RankingObservation, RankingsData
from ranking_alerts.providers import DeliveryError
from ranking_alerts.source import RankingSourceError, RawDisciplineRanking, RawRankingObservation
from ranking_alerts.storage import load_alert_state, load_rankings


def observation(
    ranking_date: str,
    *,
    singles_rank: int = 2000,
    singles_points: int = 5,
    doubles_rank: int = 1900,
    doubles_points: int = 6,
    source: str = "atptour",
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
        source=source,
    )


class FakeSource:
    def __init__(self, value: RankingObservation):
        self.value = value

    def fetch(self) -> RankingObservation:
        return self.value


class RawFakeSource:
    name = "atp-pdf"

    def __init__(self, value: RawRankingObservation):
        self.value = value

    def fetch(self) -> RawRankingObservation:
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

    def test_provider_change_with_same_sporting_content_is_unchanged(self) -> None:
        original = observation("2026-09-01")
        self.collect(original, "2026-09-01T12:00:00Z")

        outcome = self.collect(
            replace(original, source="atp-pdf"),
            "2026-09-01T13:00:00Z",
        )

        self.assertEqual("unchanged", outcome.snapshot_status)
        self.assertEqual("atptour", outcome.snapshot.source)
        self.assertEqual(1, len(outcome.rankings.snapshots))

    def test_sent_date_without_effective_delta_does_not_create_correction(self) -> None:
        self.collect(observation("2026-09-01"), "2026-09-01T12:00:00Z")
        changed = self.collect(
            observation("2026-09-08", singles_rank=1990),
            "2026-09-08T12:00:00Z",
        )
        sent_item = replace(
            changed.state.outbox[0],
            status="sent",
            sent_at="2026-09-08T12:05:00Z",
        )

        outcome = update_rankings.plan_collection(
            changed.rankings,
            RankingAlertState(outbox=(sent_item,)),
            observation("2026-09-08", singles_rank=2000),
            captured_at="2026-09-08T13:00:00Z",
        )

        self.assertEqual("revised", outcome.snapshot_status)
        self.assertEqual("none", outcome.outbox_status)
        self.assertEqual((sent_item,), outcome.state.outbox)

    def test_raw_source_is_converted_then_enriched_before_planning(self) -> None:
        raw = RawRankingObservation(
            source="atp-pdf",
            atp_id="B0UF",
            name="Luka Bojicic Ono",
            ranking_date="2026-09-01",
            singles=RawDisciplineRanking(status="ranked", rank=2000, points=5),
            doubles=RawDisciplineRanking(status="ranked", rank=1900, points=6),
        )
        enriched = replace(observation("2026-09-01"), source="atp-pdf")
        baseline_path = Path(self.temp_dir.name) / "baseline.json"

        with patch.object(update_rankings, "enrich_with_baseline", return_value=enriched) as enrich:
            converted = update_rankings._observation_from_source(
                RawFakeSource(raw),
                RankingsData(),
                baseline_path=baseline_path,
            )

        self.assertEqual(enriched, converted)
        supplied = enrich.call_args.args[0]
        self.assertEqual("atp-pdf", supplied.source)
        self.assertIsNone(supplied.singles.career_high_rank)
        enrich.assert_called_once_with(supplied, history=(), baseline_path=baseline_path)

    def test_raw_source_rejects_provider_name_mismatch_and_stale_date(self) -> None:
        raw = RawRankingObservation(
            source="atp-pdf",
            atp_id="B0UF",
            name="Luka Bojicic Ono",
            ranking_date="2026-09-01",
            singles=RawDisciplineRanking(status="ranked", rank=2000, points=5),
            doubles=RawDisciplineRanking(status="ranked", rank=1900, points=6),
        )
        mismatched = RawFakeSource(raw)
        mismatched.name = "different-provider"
        with self.assertRaisesRegex(RankingSourceError, "ranking_source_identity_mismatch"):
            update_rankings._observation_from_source(
                mismatched,
                RankingsData(),
                baseline_path=Path(self.temp_dir.name) / "baseline.json",
            )

        latest = self.collect(observation("2026-09-08"), "2026-09-08T12:00:00Z")
        with self.assertRaisesRegex(RankingSourceError, "ranking_source_stale"):
            update_rankings._observation_from_source(
                RawFakeSource(raw),
                latest.rankings,
                baseline_path=Path(self.temp_dir.name) / "baseline.json",
            )

    def test_invalid_baseline_leaves_rankings_and_outbox_byte_for_byte_unchanged(self) -> None:
        self.collect(observation("2026-09-01"), "2026-09-01T12:00:00Z")
        before_rankings = self.rankings_path.read_bytes()
        before_state = self.state_path.read_bytes()
        raw = RawRankingObservation(
            source="atp-pdf",
            atp_id="B0UF",
            name="Luka Bojicic Ono",
            ranking_date="2026-09-08",
            singles=RawDisciplineRanking(status="ranked", rank=1990, points=7),
            doubles=RawDisciplineRanking(status="ranked", rank=1900, points=6),
        )

        with self.assertRaisesRegex(
            update_rankings.CareerHighBaselineError,
            "career_high_baseline_invalid",
        ):
            update_rankings.collect(
                source=RawFakeSource(raw),
                rankings_path=self.rankings_path,
                state_path=self.state_path,
                baseline_path=Path(self.temp_dir.name) / "missing-baseline.json",
                captured_at="2026-09-08T12:00:00Z",
            )

        self.assertEqual(before_rankings, self.rankings_path.read_bytes())
        self.assertEqual(before_state, self.state_path.read_bytes())

    def test_cli_requires_explicit_source_and_keeps_fixture_path(self) -> None:
        parser = update_rankings.build_parser()
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["collect"])

        selected = parser.parse_args(["collect", "--source", "atp-pdf"])
        fixture = parser.parse_args(["dry-run", "--fixture", "ranking.json"])

        self.assertEqual("atp-pdf", selected.source)
        self.assertEqual("ranking.json", fixture.fixture)

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
