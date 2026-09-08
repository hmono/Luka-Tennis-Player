from __future__ import annotations

import unittest
from pathlib import Path

from scripts.ranking_alerts.pdf_parser import (
    PdfExtractionError,
    RankingReportParseError,
    extract_pdf_text,
    parse_ranking_report,
)


FIXTURES = Path(__file__).parent / "fixtures"


def report(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class RankingReportParserTests(unittest.TestCase):
    def test_parses_exact_player_with_tied_rank_and_thousands_separators(self) -> None:
        parsed = parse_ranking_report(
            report("pdf_ranking_report_valid.txt"),
            "singles",
            "LUKA BOJIČIĆ ONO",
        )

        self.assertEqual("singles", parsed.discipline)
        self.assertEqual("2026-09-01", parsed.ranking_date)
        self.assertEqual("Luka Bojicic Ono", parsed.player_name)
        self.assertEqual(1973, parsed.rank)
        self.assertEqual(1234, parsed.points)

    def test_tied_rank_suffix_is_converted_to_integer(self) -> None:
        text = """ATP Doubles Rankings
        Rankings as of 1 September 2026
        Rank  Player  Points
        18T  Luka Bojicic Ono  12\u202f345
        """

        parsed = parse_ranking_report(text, "doubles", "Luka Bojicic Ono")

        self.assertEqual("2026-09-01", parsed.ranking_date)
        self.assertEqual(18, parsed.rank)
        self.assertEqual(12345, parsed.points)

    def test_missing_or_ambiguous_date_fails_closed(self) -> None:
        template = """ATP Singles Rankings
        {date_lines}
        Rank  Player  Points
        1  Luka Bojicic Ono  7
        """
        for date_lines, code in (
            ("", "ranking_report_date_missing"),
            ("Ranking Date: 2026-09-01\nAs of: 2026-09-08", "ranking_report_date_ambiguous"),
        ):
            with self.subTest(code=code):
                with self.assertRaisesRegex(RankingReportParseError, code):
                    parse_ranking_report(template.format(date_lines=date_lines), "singles", "Luka Bojicic Ono")

    def test_missing_player_and_ambiguous_player_fail_closed(self) -> None:
        missing = """ATP Singles Rankings
        Ranking Date: 2026-09-01
        Rank  Player  Points
        1  Another Player  7
        """
        with self.assertRaisesRegex(RankingReportParseError, "ranking_report_player_missing"):
            parse_ranking_report(missing, "singles", "Luka Bojicic Ono")
        with self.assertRaisesRegex(RankingReportParseError, "ranking_report_player_ambiguous"):
            parse_ranking_report(report("pdf_ranking_report_duplicate_player.txt"), "doubles", "Luka Bojicic Ono")

    def test_missing_rank_or_points_and_changed_layout_fail_closed(self) -> None:
        for text, code in (
            ("""ATP Singles Rankings
            Ranking Date: 2026-09-01
            Rank  Player  Points
            Luka Bojicic Ono  7
            """, "ranking_report_row_invalid"),
            ("""ATP Singles Rankings
            Ranking Date: 2026-09-01
            Rank  Player  Points
            7  Luka Bojicic Ono
            """, "ranking_report_row_invalid"),
            (report("pdf_ranking_report_changed_layout.txt"), "ranking_report_layout_changed"),
        ):
            with self.subTest(code=code):
                with self.assertRaisesRegex(RankingReportParseError, code):
                    parse_ranking_report(text, "singles", "Luka Bojicic Ono")

    def test_exact_normalized_player_match_does_not_accept_a_longer_name(self) -> None:
        text = """ATP Singles Rankings
        Ranking Date: 2026-09-01
        Rank  Player  Points
        1  Luka Bojicic Ono Jr  7
        """

        with self.assertRaisesRegex(RankingReportParseError, "ranking_report_player_missing"):
            parse_ranking_report(text, "singles", "Luka Bojicic Ono")


class PdfTextExtractionTests(unittest.TestCase):
    def test_rejects_non_pdf_and_pdf_without_eof_marker(self) -> None:
        for value in (b"not a pdf", b"%PDF-1.7\ncontent"):
            with self.subTest(value=value):
                with self.assertRaises(PdfExtractionError) as raised:
                    extract_pdf_text(value)
                self.assertEqual("pdf_invalid", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
