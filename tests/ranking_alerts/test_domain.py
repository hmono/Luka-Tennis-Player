from __future__ import annotations

import unittest

from scripts.ranking_alerts.domain import (
    DisciplineRanking,
    DomainValidationError,
    OutboxItem,
    RankingAlertState,
    RankingObservation,
    RankingsData,
    build_snapshot,
    compare_snapshots,
    event_id,
    format_message,
    rankings_from_dict,
    rankings_to_dict,
    snapshot_from_dict,
    snapshot_id,
    snapshot_to_dict,
    state_from_dict,
    state_to_dict,
)


CAPTURED_AT = "2026-09-01T12:00:00Z"


def discipline(
    *,
    rank: int | None,
    points: int,
    career_high_rank: int | None = None,
    career_high_date: str | None = None,
) -> DisciplineRanking:
    return DisciplineRanking(
        rank=rank,
        points=points,
        career_high_rank=career_high_rank,
        career_high_date=career_high_date,
    )


def observation(
    *,
    ranking_date: str = "2026-09-01",
    singles_rank: int | None = 1973,
    singles_points: int = 5,
    singles_high: int | None = 1827,
    doubles_rank: int | None = 1825,
    doubles_points: int = 6,
    doubles_high: int | None = 1784,
) -> RankingObservation:
    return RankingObservation(
        atp_id="B0UF",
        name="Luka Bojicic Ono",
        ranking_date=ranking_date,
        source="atptour",
        singles=discipline(
            rank=singles_rank,
            points=singles_points,
            career_high_rank=singles_high,
            career_high_date="2025-12-01" if singles_high is not None else None,
        ),
        doubles=discipline(
            rank=doubles_rank,
            points=doubles_points,
            career_high_rank=doubles_high,
            career_high_date="2025-07-28" if doubles_high is not None else None,
        ),
    )


def snapshot(**kwargs):
    captured_at = kwargs.pop("captured_at", CAPTURED_AT)
    return build_snapshot(observation(**kwargs), captured_at=captured_at)


class DisciplineValidationTests(unittest.TestCase):
    def test_accepts_ranked_and_unranked_values(self) -> None:
        ranked = discipline(rank=20, points=100, career_high_rank=10)
        unranked = discipline(rank=None, points=0, career_high_rank=10)

        self.assertEqual(20, ranked.rank)
        self.assertIsNone(unranked.rank)

    def test_rejects_zero_or_negative_rank(self) -> None:
        for invalid_rank in (0, -1):
            with self.subTest(rank=invalid_rank):
                with self.assertRaises(DomainValidationError):
                    discipline(rank=invalid_rank, points=0)

    def test_rejects_negative_points(self) -> None:
        with self.assertRaises(DomainValidationError):
            discipline(rank=100, points=-1)

    def test_rejects_career_high_worse_than_current_rank(self) -> None:
        with self.assertRaises(DomainValidationError):
            discipline(rank=100, points=1, career_high_rank=101)

    def test_rejects_invalid_career_high_date(self) -> None:
        with self.assertRaises(DomainValidationError):
            discipline(
                rank=100,
                points=1,
                career_high_rank=90,
                career_high_date="01/09/2026",
            )


class SourceValidationTests(unittest.TestCase):
    def test_accepts_legacy_and_pdf_source_names(self) -> None:
        legacy = observation()
        pdf = RankingObservation(
            atp_id=legacy.atp_id,
            name=legacy.name,
            ranking_date=legacy.ranking_date,
            singles=legacy.singles,
            doubles=legacy.doubles,
            source="atp-pdf",
        )

        self.assertEqual("atptour", legacy.source)
        self.assertEqual("atp-pdf", pdf.source)

    def test_rejects_unsafe_source_name(self) -> None:
        legacy = observation()
        with self.assertRaisesRegex(DomainValidationError, "invalid_source"):
            RankingObservation(
                atp_id=legacy.atp_id,
                name=legacy.name,
                ranking_date=legacy.ranking_date,
                singles=legacy.singles,
                doubles=legacy.doubles,
                source="ATP PDF/../../",
            )

class SnapshotIdentityTests(unittest.TestCase):
    def test_snapshot_id_is_stable_and_excludes_capture_time(self) -> None:
        item = observation()
        first = build_snapshot(item, captured_at="2026-09-01T12:00:00Z")
        later_capture = build_snapshot(item, captured_at="2026-09-01T18:00:00Z")

        self.assertEqual(first.id, later_capture.id)
        self.assertEqual(snapshot_id(item), first.id)
        self.assertRegex(first.id, r"^sha256:[0-9a-f]{64}$")

    def test_canonical_value_change_changes_snapshot_id(self) -> None:
        initial = snapshot_id(observation(singles_points=5))
        changed = snapshot_id(observation(singles_points=6))

        self.assertNotEqual(initial, changed)

    def test_event_id_is_stable_per_snapshot_and_event_type(self) -> None:
        current_id = snapshot().id

        first = event_id(current_id, "ranking_change")
        second = event_id(current_id, "ranking_change")
        correction = event_id(current_id, "ranking_correction")

        self.assertEqual(first, second)
        self.assertNotEqual(first, correction)
        self.assertRegex(first, r"^sha256:[0-9a-f]{64}$")

    def test_build_snapshot_records_revision_without_changing_canonical_id(self) -> None:
        item = observation()
        original = build_snapshot(item, captured_at=CAPTURED_AT)
        revision = build_snapshot(
            item,
            captured_at="2026-09-01T13:00:00Z",
            source_revision_of=original.id,
        )

        self.assertEqual(original.id, revision.id)
        self.assertEqual(original.id, revision.source_revision_of)

    def test_rejects_invalid_ranking_date_and_capture_timestamp(self) -> None:
        with self.assertRaises(DomainValidationError):
            observation(ranking_date="2026/09/01")
        with self.assertRaises(DomainValidationError):
            build_snapshot(observation(), captured_at="2026-09-01 12:00:00")


class DeltaTests(unittest.TestCase):
    def test_rank_delta_sign_and_points_delta(self) -> None:
        previous = snapshot(singles_rank=2000, singles_points=4)
        current = snapshot(
            ranking_date="2026-09-08",
            singles_rank=1973,
            singles_points=6,
            captured_at="2026-09-08T12:00:00Z",
        )

        delta = compare_snapshots(previous, current)

        self.assertEqual(27, delta.singles.rank_delta)
        self.assertEqual(2, delta.singles.points_delta)
        self.assertTrue(delta.has_changes)

    def test_rank_drop_has_negative_delta(self) -> None:
        previous = snapshot(singles_rank=1973)
        current = snapshot(
            ranking_date="2026-09-08",
            singles_rank=2000,
            singles_high=1827,
            captured_at="2026-09-08T12:00:00Z",
        )

        delta = compare_snapshots(previous, current)

        self.assertEqual(-27, delta.singles.rank_delta)

    def test_entering_and_leaving_ranking_have_no_numeric_rank_delta(self) -> None:
        unranked = snapshot(singles_rank=None, singles_points=0)
        entered = snapshot(
            ranking_date="2026-09-08",
            singles_rank=2100,
            singles_points=1,
            captured_at="2026-09-08T12:00:00Z",
        )
        left = snapshot(
            ranking_date="2026-09-15",
            singles_rank=None,
            singles_points=0,
            captured_at="2026-09-15T12:00:00Z",
        )

        entry_delta = compare_snapshots(unranked, entered)
        exit_delta = compare_snapshots(entered, left)

        self.assertTrue(entry_delta.singles.entered_ranking)
        self.assertIsNone(entry_delta.singles.rank_delta)
        self.assertTrue(exit_delta.singles.left_ranking)
        self.assertIsNone(exit_delta.singles.rank_delta)

    def test_detects_changes_in_either_discipline_and_points_only(self) -> None:
        previous = snapshot()
        singles_changed = snapshot(
            ranking_date="2026-09-08",
            singles_points=6,
            captured_at="2026-09-08T12:00:00Z",
        )
        doubles_changed = snapshot(
            ranking_date="2026-09-08",
            doubles_points=7,
            captured_at="2026-09-08T12:00:00Z",
        )

        singles_delta = compare_snapshots(previous, singles_changed)
        doubles_delta = compare_snapshots(previous, doubles_changed)

        self.assertEqual(1, singles_delta.singles.points_delta)
        self.assertEqual(0, singles_delta.doubles.points_delta)
        self.assertEqual(0, doubles_delta.singles.points_delta)
        self.assertEqual(1, doubles_delta.doubles.points_delta)
        self.assertTrue(singles_delta.has_changes)
        self.assertTrue(doubles_delta.has_changes)

    def test_new_career_high_is_strictly_better_than_all_history(self) -> None:
        oldest = snapshot(
            ranking_date="2026-08-18",
            singles_rank=1900,
            singles_high=1900,
            captured_at="2026-08-18T12:00:00Z",
        )
        previous = snapshot(
            ranking_date="2026-08-25",
            singles_rank=1890,
            singles_high=1890,
            captured_at="2026-08-25T12:00:00Z",
        )
        new_high = snapshot(
            ranking_date="2026-09-01",
            singles_rank=1889,
            singles_high=1889,
        )
        tied = snapshot(
            ranking_date="2026-09-08",
            singles_rank=1889,
            singles_high=1889,
            captured_at="2026-09-08T12:00:00Z",
        )
        worse = snapshot(
            ranking_date="2026-09-08",
            singles_rank=1950,
            singles_high=1889,
            captured_at="2026-09-08T12:00:00Z",
        )

        high_delta = compare_snapshots(previous, new_high, history=(oldest, previous))
        tied_delta = compare_snapshots(new_high, tied, history=(oldest, previous, new_high))
        worse_delta = compare_snapshots(new_high, worse, history=(oldest, previous, new_high))

        self.assertEqual(1889, high_delta.singles.new_career_high)
        self.assertIsNone(tied_delta.singles.new_career_high)
        self.assertIsNone(worse_delta.singles.new_career_high)


class MessageTests(unittest.TestCase):
    def test_formats_one_aggregated_message_without_approximate_values(self) -> None:
        previous = snapshot(singles_rank=1979, singles_points=3, doubles_rank=1822)
        current = snapshot(
            ranking_date="2026-09-08",
            singles_rank=1973,
            singles_points=5,
            doubles_rank=1825,
            captured_at="2026-09-08T12:00:00Z",
        )

        message = format_message(current, compare_snapshots(previous, current))

        self.assertIn("ATP Ranking — 2026-09-08", message)
        self.assertIn("Singles: #1.973 (+6) | 5 pts (+2)", message)
        self.assertIn("Doubles: #1.825 (-3) | 6 pts (0)", message)
        self.assertNotIn("~", message)

    def test_formats_entry_and_exit_without_fabricated_rank_delta(self) -> None:
        previous = snapshot(singles_rank=None, singles_points=0, doubles_rank=1825)
        current = snapshot(
            ranking_date="2026-09-08",
            singles_rank=2100,
            singles_points=1,
            doubles_rank=None,
            doubles_points=0,
            captured_at="2026-09-08T12:00:00Z",
        )

        message = format_message(current, compare_snapshots(previous, current))

        self.assertIn("entrou no ranking", message)
        self.assertIn("saiu do ranking", message)
        singles_line = next(line for line in message.splitlines() if line.startswith("Singles:"))
        rank_part = singles_line.split(" | ", 1)[0]
        self.assertNotRegex(rank_part, r"\([+-]\d+\)")


class SerializationTests(unittest.TestCase):
    def test_snapshot_round_trip_preserves_all_fields(self) -> None:
        original = build_snapshot(
            observation(),
            captured_at=CAPTURED_AT,
            source_revision_of="sha256:" + "a" * 64,
        )

        restored = snapshot_from_dict(snapshot_to_dict(original))

        self.assertEqual(original, restored)

    def test_rankings_and_state_round_trip(self) -> None:
        current = snapshot()
        rankings = RankingsData(snapshots=(current,))
        item = OutboxItem(
            id=event_id(current.id, "ranking_change"),
            snapshot_id=current.id,
            event_type="ranking_change",
            status="pending",
            attempts=0,
            created_at=CAPTURED_AT,
            sent_at=None,
            provider="callmebot",
            last_error_code=None,
        )
        state = RankingAlertState(outbox=(item,))

        restored_rankings = rankings_from_dict(rankings_to_dict(rankings))
        restored_state = state_from_dict(state_to_dict(state))

        self.assertEqual(rankings, restored_rankings)
        self.assertEqual(state, restored_state)

    def test_rejects_invalid_schema_versions(self) -> None:
        with self.assertRaises(DomainValidationError):
            rankings_from_dict(
                {
                    "schema_version": 2,
                    "player": {"atp_id": "B0UF", "name": "Luka Bojicic Ono"},
                    "snapshots": [],
                }
            )

        with self.assertRaises(DomainValidationError):
            state_from_dict(
                {
                    "schema_version": 2,
                    "outbox": [
                        {
                            "id": "sha256:" + "a" * 64,
                            "snapshot_id": "sha256:" + "b" * 64,
                            "event_type": "ranking_change",
                            "status": "pending",
                            "attempts": 0,
                            "created_at": CAPTURED_AT,
                            "sent_at": None,
                            "provider": "callmebot",
                            "last_error_code": None,
                        }
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
