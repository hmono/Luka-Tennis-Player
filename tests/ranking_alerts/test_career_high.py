from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.ranking_alerts.career_high import (
    DEFAULT_BASELINE_PATH,
    BaselineDiscipline,
    CareerHighBaseline,
    CareerHighBaselineError,
    enrich_career_high,
    load_baseline,
    parse_baseline,
)
from scripts.ranking_alerts.domain import DisciplineRanking, RankingObservation, build_snapshot


def document(*, singles_rank: int = 2000, doubles_rank: int = 1900) -> dict:
    return {
        "schema_version": 1,
        "player": {"atp_id": "B0UF", "name": "Luka Bojicic Ono"},
        "verified_at": "2026-01-01T12:00:00Z",
        "disciplines": {
            "singles": {
                "rank": singles_rank,
                "ranking_date": "2025-12-01",
                "reference": "Manual ATP verification, 2026-01-01",
            },
            "doubles": {
                "rank": doubles_rank,
                "ranking_date": "2025-11-24",
                "reference": "Manual ATP verification, 2026-01-01",
            },
        },
    }


def observation(*, ranking_date: str, singles_rank: int | None, doubles_rank: int | None) -> RankingObservation:
    return RankingObservation(
        atp_id="B0UF",
        name="Luka Bojicic Ono",
        ranking_date=ranking_date,
        singles=DisciplineRanking(rank=singles_rank, points=5),
        doubles=DisciplineRanking(rank=doubles_rank, points=6),
    )


class CareerHighBaselineTests(unittest.TestCase):
    def test_repository_template_is_not_activatable(self) -> None:
        with self.assertRaisesRegex(CareerHighBaselineError, "^career_high_baseline_invalid$"):
            load_baseline(DEFAULT_BASELINE_PATH)

        template = json.loads(DEFAULT_BASELINE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(0, template["disciplines"]["singles"]["rank"])
        self.assertEqual(0, template["disciplines"]["doubles"]["rank"])

    def test_missing_and_placeholder_baselines_fail_closed(self) -> None:
        with self.assertRaises(CareerHighBaselineError):
            load_baseline(Path("missing-baseline.json"))
        placeholder = document()
        placeholder["disciplines"]["singles"]["rank"] = 0
        with self.assertRaises(CareerHighBaselineError):
            parse_baseline(placeholder)
        placeholder_reference = document()
        placeholder_reference["disciplines"]["singles"]["reference"] = "manual-verification-reference"
        with self.assertRaises(CareerHighBaselineError):
            parse_baseline(placeholder_reference)

    def test_invalid_or_inconsistent_baseline_fails_closed(self) -> None:
        future = document()
        future["disciplines"]["singles"]["ranking_date"] = "2026-01-02"
        with self.assertRaises(CareerHighBaselineError):
            parse_baseline(future)
        wrong_player = document()
        wrong_player["player"]["atp_id"] = "OTHER"
        with self.assertRaises(CareerHighBaselineError):
            parse_baseline(wrong_player)

    def test_loads_strict_valid_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(json.dumps(document()), encoding="utf-8")
            baseline = load_baseline(path)

        self.assertEqual(2000, baseline.singles.rank)
        self.assertEqual("2025-11-24", baseline.doubles.ranking_date)

    def test_direct_construction_cannot_bypass_validation(self) -> None:
        for invalid_rank in (True, "2000"):
            with self.subTest(rank=invalid_rank), self.assertRaises(CareerHighBaselineError):
                BaselineDiscipline(
                    rank=invalid_rank,  # type: ignore[arg-type]
                    ranking_date="2025-12-01",
                    reference="Manual ATP verification, 2026-01-01",
                )
        with self.assertRaises(CareerHighBaselineError):
            BaselineDiscipline(
                rank=2000,
                ranking_date=None,  # type: ignore[arg-type]
                reference="Manual ATP verification, 2026-01-01",
            )
        with self.assertRaises(CareerHighBaselineError):
            BaselineDiscipline(
                rank=2000,
                ranking_date="2025-12-01",
                reference=None,  # type: ignore[arg-type]
            )
        with self.assertRaises(CareerHighBaselineError):
            BaselineDiscipline(
                rank=0,
                ranking_date="2025-12-01",
                reference="Manual ATP verification, 2026-01-01",
            )
        with self.assertRaises(CareerHighBaselineError):
            BaselineDiscipline(
                rank=2000,
                ranking_date="2025-12-01",
                reference="unverified",
            )

        singles = BaselineDiscipline(
            rank=2000,
            ranking_date="2025-12-01",
            reference="Manual ATP verification, 2026-01-01",
        )
        doubles = BaselineDiscipline(
            rank=1900,
            ranking_date="2025-11-24",
            reference="Manual ATP verification, 2026-01-01",
        )
        for invalid_verified_at in (None, "INVALID"):
            with self.subTest(verified_at=invalid_verified_at), self.assertRaises(CareerHighBaselineError):
                CareerHighBaseline(
                    verified_at=invalid_verified_at,  # type: ignore[arg-type]
                    singles=singles,
                    doubles=doubles,
                )
        with self.assertRaises(CareerHighBaselineError):
            CareerHighBaseline(
                verified_at="2025-11-01T12:00:00Z",
                singles=singles,
                doubles=doubles,
            )

        with self.assertRaises(CareerHighBaselineError):
            CareerHighBaseline(
                verified_at="2026-01-01T12:00:00Z",
                singles="not-a-discipline",  # type: ignore[arg-type]
                doubles=doubles,
            )


class CareerHighEnrichmentTests(unittest.TestCase):
    def test_new_high_uses_current_ranking_date(self) -> None:
        baseline = parse_baseline(document())
        value = observation(ranking_date="2026-02-02", singles_rank=1999, doubles_rank=1899)

        enriched = enrich_career_high(value, baseline=baseline)

        self.assertEqual((1999, "2026-02-02"), (enriched.singles.career_high_rank, enriched.singles.career_high_date))
        self.assertEqual((1899, "2026-02-02"), (enriched.doubles.career_high_rank, enriched.doubles.career_high_date))

    def test_tie_preserves_first_historical_date(self) -> None:
        baseline = parse_baseline(document(singles_rank=2000))
        earlier = build_snapshot(
            observation(ranking_date="2026-01-05", singles_rank=1900, doubles_rank=1900),
            captured_at="2026-01-05T12:00:00Z",
        )
        value = observation(ranking_date="2026-02-02", singles_rank=1900, doubles_rank=1950)

        enriched = enrich_career_high(value, baseline=baseline, history=(earlier,))

        self.assertEqual(1900, enriched.singles.career_high_rank)
        self.assertEqual("2026-01-05", enriched.singles.career_high_date)

    def test_legacy_derived_highs_are_not_promoted(self) -> None:
        baseline = parse_baseline(document(singles_rank=2000, doubles_rank=1900))
        legacy_observation = RankingObservation(
            atp_id="B0UF",
            name="Luka Bojicic Ono",
            ranking_date="2026-01-05",
            singles=DisciplineRanking(
                rank=1900,
                points=5,
                career_high_rank=1827,
                career_high_date="2025-12-01",
            ),
            doubles=DisciplineRanking(
                rank=1890,
                points=6,
                career_high_rank=1784,
                career_high_date="2025-07-28",
            ),
        )
        legacy = build_snapshot(
            legacy_observation,
            captured_at="2026-01-05T12:00:00Z",
        )
        value = observation(ranking_date="2026-02-02", singles_rank=1950, doubles_rank=1895)

        enriched = enrich_career_high(value, baseline=baseline, history=(legacy,))

        self.assertEqual((1900, "2026-01-05"), (enriched.singles.career_high_rank, enriched.singles.career_high_date))
        self.assertEqual((1890, "2026-01-05"), (enriched.doubles.career_high_rank, enriched.doubles.career_high_date))

    def test_baseline_date_is_preserved_when_current_rank_is_worse(self) -> None:
        baseline = parse_baseline(document())
        value = observation(ranking_date="2026-02-02", singles_rank=2100, doubles_rank=None)

        enriched = enrich_career_high(value, baseline=baseline)

        self.assertEqual((2000, "2025-12-01"), (enriched.singles.career_high_rank, enriched.singles.career_high_date))
        self.assertEqual((1900, "2025-11-24"), (enriched.doubles.career_high_rank, enriched.doubles.career_high_date))

    def test_baseline_date_is_preserved_on_current_tie(self) -> None:
        baseline = parse_baseline(document())
        value = observation(ranking_date="2026-02-02", singles_rank=2000, doubles_rank=1900)

        enriched = enrich_career_high(value, baseline=baseline)

        self.assertEqual((2000, "2025-12-01"), (enriched.singles.career_high_rank, enriched.singles.career_high_date))
        self.assertEqual((1900, "2025-11-24"), (enriched.doubles.career_high_rank, enriched.doubles.career_high_date))

    def test_inconsistent_history_or_future_baseline_fails_closed(self) -> None:
        baseline = parse_baseline(document())
        value = observation(ranking_date="2026-02-02", singles_rank=2100, doubles_rank=2000)
        inconsistent_observation = RankingObservation(
            atp_id="B0UF",
            name="Luka Bojicic Ono",
            ranking_date="2026-01-05",
            singles=DisciplineRanking(rank=2050, points=5, career_high_rank=2000),
            doubles=DisciplineRanking(rank=1950, points=6),
        )
        inconsistent = build_snapshot(
            inconsistent_observation,
            captured_at="2026-01-05T12:00:00Z",
        )
        with self.assertRaises(CareerHighBaselineError):
            enrich_career_high(value, baseline=baseline, history=(inconsistent,))
        future_baseline = parse_baseline(document())
        future_value = observation(ranking_date="2025-11-30", singles_rank=2100, doubles_rank=2000)
        with self.assertRaises(CareerHighBaselineError):
            enrich_career_high(future_value, baseline=future_baseline)

    def test_future_historical_career_high_date_fails_closed(self) -> None:
        baseline = parse_baseline(document())
        value = observation(ranking_date="2026-02-02", singles_rank=2100, doubles_rank=2000)
        inconsistent_observation = RankingObservation(
            atp_id="B0UF",
            name="Luka Bojicic Ono",
            ranking_date="2026-01-05",
            singles=DisciplineRanking(
                rank=2050,
                points=5,
                career_high_rank=1900,
                career_high_date="2026-01-12",
            ),
            doubles=DisciplineRanking(rank=1950, points=6),
        )
        inconsistent = build_snapshot(
            inconsistent_observation,
            captured_at="2026-01-05T12:00:00Z",
        )

        with self.assertRaises(CareerHighBaselineError):
            enrich_career_high(value, baseline=baseline, history=(inconsistent,))


if __name__ == "__main__":
    unittest.main()
