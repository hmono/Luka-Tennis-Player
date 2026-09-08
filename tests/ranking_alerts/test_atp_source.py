from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.ranking_alerts.atp_source import AtpSourceError, normalize_dom, normalize_payload


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with (FIXTURES / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class AtpPayloadNormalizationTests(unittest.TestCase):
    def test_valid_fixture_normalizes_complete_observation(self) -> None:
        result = normalize_payload(load_fixture("atp_rankings_valid.json"))

        self.assertEqual("B0UF", result.atp_id)
        self.assertEqual("Luka Bojicic Ono", result.name)
        self.assertEqual("2026-09-01", result.ranking_date)
        self.assertEqual("atptour", result.source)
        self.assertEqual(1973, result.singles.rank)
        self.assertEqual(5, result.singles.points)
        self.assertEqual(1827, result.singles.career_high_rank)
        self.assertEqual("2025-12-01", result.singles.career_high_date)
        self.assertEqual(1825, result.doubles.rank)
        self.assertEqual(6, result.doubles.points)
        self.assertEqual(1784, result.doubles.career_high_rank)

    def test_missing_doubles_fails_closed(self) -> None:
        with self.assertRaises(AtpSourceError) as raised:
            normalize_payload(load_fixture("atp_rankings_missing_doubles.json"))

        self.assertEqual("atp_incomplete_observation", raised.exception.code)

    def test_changed_shape_fails_closed(self) -> None:
        with self.assertRaises(AtpSourceError) as raised:
            normalize_payload(load_fixture("atp_rankings_changed_shape.json"))

        self.assertEqual("atp_schema_changed", raised.exception.code)

    def test_player_id_mismatch_fails_closed(self) -> None:
        payload = load_fixture("atp_rankings_valid.json")
        payload["player"]["atp_id"] = "WRONG"

        with self.assertRaises(AtpSourceError) as raised:
            normalize_payload(payload)

        self.assertEqual("atp_identity_mismatch", raised.exception.code)

    def test_player_name_is_compared_case_and_diacritic_insensitively(self) -> None:
        payload = load_fixture("atp_rankings_valid.json")
        payload["player"]["name"] = "LUKA BOJIČIĆ ONO"

        result = normalize_payload(payload)

        self.assertEqual("LUKA BOJIČIĆ ONO", result.name)

    def test_zero_rank_is_normalized_to_none(self) -> None:
        payload = load_fixture("atp_rankings_valid.json")
        payload["rankings"]["singles"].update(
            {
                "rank": 0,
                "points": 0,
                "career_high_rank": 1827,
                "career_high_date": "2025-12-01",
            }
        )

        result = normalize_payload(payload)

        self.assertIsNone(result.singles.rank)
        self.assertEqual(0, result.singles.points)

    def test_missing_points_is_not_invented_for_unranked_player(self) -> None:
        payload = load_fixture("atp_rankings_valid.json")
        payload["rankings"]["singles"]["rank"] = 0
        del payload["rankings"]["singles"]["points"]

        with self.assertRaises(AtpSourceError) as raised:
            normalize_payload(payload)

        self.assertEqual("atp_incomplete_observation", raised.exception.code)

    def test_missing_or_ambiguous_ranking_date_fails_closed(self) -> None:
        missing = load_fixture("atp_rankings_valid.json")
        del missing["ranking_date"]
        ambiguous = copy.deepcopy(missing)
        ambiguous["ranking_dates"] = ["2026-09-01", "2026-09-08"]

        for payload in (missing, ambiguous):
            with self.subTest(payload=payload):
                with self.assertRaises(AtpSourceError) as raised:
                    normalize_payload(payload)
                self.assertIn(
                    raised.exception.code,
                    {"atp_incomplete_observation", "atp_schema_changed"},
                )
    def test_dom_fallback_extracts_complete_observation(self) -> None:
        singles = """
        Luka Bojicic Ono
        Career 1.827 Career High Rank (2025-12-01)
        Refresh 1.973 Rank 5 Points
        """
        doubles = """
        Luka Bojicic Ono
        Career 1.784 Career High Rank (2025-07-28)
        Refresh 1.825 Rank 6 Points
        """
        history = """
        Luka Bojicic Ono
        Singles Doubles
        2026-09-01 1.973
        """

        result = normalize_dom(
            singles_text=singles,
            doubles_text=doubles,
            history_text=history,
        )

        self.assertEqual("2026-09-01", result.ranking_date)
        self.assertEqual(1973, result.singles.rank)
        self.assertEqual(5, result.singles.points)
        self.assertEqual(1825, result.doubles.rank)
        self.assertEqual(6, result.doubles.points)


    def test_incompatible_career_high_fails_closed(self) -> None:
        payload = load_fixture("atp_rankings_valid.json")
        payload["rankings"]["singles"]["career_high_rank"] = 2000

        with self.assertRaises(AtpSourceError):
            normalize_payload(payload)


if __name__ == "__main__":
    unittest.main()
