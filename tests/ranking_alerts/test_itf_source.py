from __future__ import annotations

import unittest

from scripts.ranking_alerts.itf_source import (
    ItfOverviewResponse,
    ItfProfileCapture,
    ItfRankingSource,
    overview_path,
    parse_capture,
)
from scripts.ranking_alerts.source import RankingSourceError

TITLE = "Luka Bojicic Ono Tennis Player Profile | ITF"

# Sanitized copies of the 2026-09-24 qualification probe replies.
SINGLES_PAYLOAD = {
    "rankings": [
        {"name": "ATP Singles Ranking", "rank": 2205, "date": "21 September 2026"},
        {"name": "World Tennis Singles Ranking", "rank": 379, "date": "21 September 2026"},
    ],
    "careerHighRankings": [
        {"name": "ATP Singles Ranking", "rank": 1827, "date": "01 December 2025"},
        {"name": "World Tennis Singles Ranking", "rank": 338, "date": "06 July 2026"},
    ],
    "years": [2026, 2025],
    "title": "Professional win-loss record",
}
DOUBLES_PAYLOAD = {
    "rankings": [{"name": "ATP Doubles Ranking", "rank": 1460, "date": "21 September 2026"}],
    "careerHighRankings": [{"name": "ATP Doubles Ranking", "rank": 1407, "date": "22 June 2026"}],
    "years": [2026, 2025],
    "title": "Professional win-loss record",
}


def capture(
    *,
    title: str = TITLE,
    singles: object = SINGLES_PAYLOAD,
    doubles: object = DOUBLES_PAYLOAD,
    singles_status: int = 200,
    doubles_status: int = 200,
) -> ItfProfileCapture:
    return ItfProfileCapture(
        page_title=title,
        singles=ItfOverviewResponse(status=singles_status, payload=singles),
        doubles=ItfOverviewResponse(status=doubles_status, payload=doubles),
    )


class ItfParserTests(unittest.TestCase):
    def test_valid_capture_normalizes_both_disciplines_without_points(self) -> None:
        observation = parse_capture(capture())

        self.assertEqual("itf", observation.source)
        self.assertEqual("B0UF", observation.atp_id)
        self.assertEqual("2026-09-21", observation.ranking_date)
        self.assertEqual(("ranked", 2205, None), (observation.singles.status, observation.singles.rank, observation.singles.points))
        self.assertEqual(("ranked", 1460, None), (observation.doubles.status, observation.doubles.rank, observation.doubles.points))

    def test_endpoints_are_fixed_per_discipline(self) -> None:
        self.assertIn("matchTypeCode=S", overview_path("singles"))
        self.assertIn("matchTypeCode=D", overview_path("doubles"))
        self.assertIn("playerId=800625103", overview_path("singles"))

    def test_identity_mismatch_when_profile_belongs_to_another_player(self) -> None:
        with self.assertRaises(RankingSourceError) as raised:
            parse_capture(capture(title="Someone Else Tennis Player Profile | ITF"))
        self.assertEqual("ranking_source_identity_mismatch", raised.exception.code)

    def test_http_statuses_map_to_sanitized_codes(self) -> None:
        for status, code in ((403, "ranking_source_blocked"), (429, "ranking_source_rate_limited"), (500, "ranking_source_incomplete")):
            with self.subTest(status=status), self.assertRaises(RankingSourceError) as raised:
                parse_capture(capture(singles=None, singles_status=status))
            self.assertEqual(code, raised.exception.code)

    def test_missing_atp_entry_in_well_formed_reply_is_unranked(self) -> None:
        observation = parse_capture(capture(doubles={"rankings": [], "careerHighRankings": []}))

        self.assertEqual("unranked", observation.doubles.status)
        self.assertIsNone(observation.doubles.rank)
        self.assertEqual("2026-09-21", observation.ranking_date)

    def test_malformed_reply_fails_closed(self) -> None:
        for payload in (None, "html", {"rankings": "x"}, {"other": []}):
            with self.subTest(payload=payload), self.assertRaises(RankingSourceError) as raised:
                parse_capture(capture(doubles=payload))
            self.assertEqual("ranking_source_schema_changed", raised.exception.code)

    def test_invalid_rank_or_date_fails_closed(self) -> None:
        for entry in (
            {"name": "ATP Doubles Ranking", "rank": 0, "date": "21 September 2026"},
            {"name": "ATP Doubles Ranking", "rank": "1460", "date": "21 September 2026"},
            {"name": "ATP Doubles Ranking", "rank": True, "date": "21 September 2026"},
            {"name": "ATP Doubles Ranking", "rank": 1460, "date": "2026-09-21"},
            {"name": "ATP Doubles Ranking", "rank": 1460, "date": None},
        ):
            with self.subTest(entry=entry), self.assertRaises(RankingSourceError) as raised:
                parse_capture(capture(doubles={"rankings": [entry]}))
            self.assertEqual("ranking_source_schema_changed", raised.exception.code)

    def test_duplicate_atp_entries_fail_closed(self) -> None:
        payload = {"rankings": DOUBLES_PAYLOAD["rankings"] * 2}
        with self.assertRaises(RankingSourceError) as raised:
            parse_capture(capture(doubles=payload))
        self.assertEqual("ranking_source_schema_changed", raised.exception.code)

    def test_disciplines_from_different_publications_are_incomplete(self) -> None:
        payload = {"rankings": [{"name": "ATP Doubles Ranking", "rank": 1460, "date": "14 September 2026"}]}
        with self.assertRaises(RankingSourceError) as raised:
            parse_capture(capture(doubles=payload))
        self.assertEqual("ranking_source_incomplete", raised.exception.code)

    def test_no_official_date_at_all_is_incomplete(self) -> None:
        empty = {"rankings": []}
        with self.assertRaises(RankingSourceError) as raised:
            parse_capture(capture(singles=empty, doubles=empty))
        self.assertEqual("ranking_source_incomplete", raised.exception.code)


class ItfSourceTests(unittest.TestCase):
    def test_source_name_matches_observation_provenance(self) -> None:
        source = ItfRankingSource(capture=lambda timeout: capture())

        observation = source.fetch()

        self.assertEqual(source.name, observation.source)

    def test_browser_failures_are_redacted(self) -> None:
        class TimeoutError(Exception):  # noqa: A001 - mimics playwright's class name
            pass

        def timing_out(timeout: float) -> ItfProfileCapture:
            raise TimeoutError("secret-host-details")

        def crashing(timeout: float) -> ItfProfileCapture:
            raise RuntimeError("secret-cookie-details")

        with self.assertRaises(RankingSourceError) as raised:
            ItfRankingSource(capture=timing_out).fetch()
        self.assertEqual("ranking_source_timeout", raised.exception.code)
        self.assertNotIn("secret", str(raised.exception))

        with self.assertRaises(RankingSourceError) as raised:
            ItfRankingSource(capture=crashing).fetch()
        self.assertEqual("ranking_source_incomplete", raised.exception.code)
        self.assertNotIn("secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
