from __future__ import annotations

import unittest

from scripts.ranking_alerts.source import (
    RANKING_SOURCE_ERROR_CODES,
    RankingSourceError,
    RawDisciplineRanking,
    RawRankingObservation,
)


class SourceContractTests(unittest.TestCase):
    def test_raw_observation_has_no_career_high_dependency(self) -> None:
        observation = RawRankingObservation(
            source="candidate-provider",
            atp_id="B0UF",
            name="Luka Bojicic Ono",
            ranking_date="2026-09-01",
            singles=RawDisciplineRanking(status="ranked", rank=2101, points=4),
            doubles=RawDisciplineRanking(status="unranked", rank=None, points=0),
        )

        self.assertEqual("candidate-provider", observation.source)
        self.assertEqual(2101, observation.singles.rank)
        self.assertIsNone(observation.doubles.rank)

    def test_ranked_requires_positive_integer_rank(self) -> None:
        for invalid_rank in (None, 0, -1, True, 1.5, "1"):
            with self.subTest(rank=invalid_rank), self.assertRaises(ValueError) as raised:
                RawDisciplineRanking(status="ranked", rank=invalid_rank, points=0)  # type: ignore[arg-type]

            self.assertEqual("invalid_ranked_rank", str(raised.exception))

    def test_unranked_requires_none_rank(self) -> None:
        with self.assertRaises(ValueError) as raised:
            RawDisciplineRanking(status="unranked", rank=2101, points=0)

        self.assertEqual("invalid_unranked_rank", str(raised.exception))

    def test_status_is_explicit_and_closed(self) -> None:
        with self.assertRaises(ValueError) as raised:
            RawDisciplineRanking(status="missing", rank=None, points=0)  # type: ignore[arg-type]

        self.assertEqual("invalid_ranking_status", str(raised.exception))

    def test_points_require_non_negative_integer(self) -> None:
        for invalid_points in (-1, True, 1.5, "1", None):
            with self.subTest(points=invalid_points), self.assertRaises(ValueError) as raised:
                RawDisciplineRanking(status="unranked", rank=None, points=invalid_points)  # type: ignore[arg-type]

            self.assertEqual("invalid_ranking_points", str(raised.exception))

    def test_public_errors_are_stable_codes_only(self) -> None:
        error = RankingSourceError("ranking_source_rate_limited")

        self.assertEqual("ranking_source_rate_limited", error.code)
        self.assertEqual("ranking_source_rate_limited", str(error))
        self.assertIn(error.code, RANKING_SOURCE_ERROR_CODES)
        self.assertIn("ranking_source_stale", RANKING_SOURCE_ERROR_CODES)

    def test_unknown_error_code_is_rejected_without_echoing_input(self) -> None:
        with self.assertRaises(ValueError) as raised:
            RankingSourceError("token=should-not-be-echoed")

        self.assertEqual("invalid_ranking_source_error_code", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
