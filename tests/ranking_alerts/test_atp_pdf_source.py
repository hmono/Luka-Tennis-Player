from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from probe_atp_pdfs import probe
from scripts.ranking_alerts.atp_pdf_source import (
    DOUBLES_ALPHA_PDF_URL,
    MAX_PDF_BYTES,
    SINGLES_ALPHA_PDF_URL,
    AtpPdfRankingSource,
    download_pdf,
)
from scripts.ranking_alerts.pdf_parser import ParsedRankingReport
from scripts.ranking_alerts.source import (
    RankingSourceError,
    RawDisciplineRanking,
    RawRankingObservation,
)


_VALID_PDF = b"%PDF-1.7\nminimal\n%%EOF"


class _Response:
    def __init__(self, body: bytes = _VALID_PDF, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.body = body
        self.status = status
        self.headers = {"Content-Type": "application/pdf", **(headers or {})}
        self.read_sizes: list[int] = []

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        return self.body


class AtpPdfDownloadTests(unittest.TestCase):
    def test_uses_fixed_official_alpha_urls(self) -> None:
        self.assertEqual(
            "https://www.atptour.com/-/media/files/rankings-and-stats/singles_entry_alpha.pdf",
            SINGLES_ALPHA_PDF_URL,
        )
        self.assertEqual(
            "https://www.atptour.com/-/media/files/rankings-and-stats/doubles_entry_alpha.pdf",
            DOUBLES_ALPHA_PDF_URL,
        )

    def test_download_requests_pdf_and_enforces_byte_magic_and_eof(self) -> None:
        requests: list[object] = []

        def opener(request: object, *, timeout: float) -> _Response:
            requests.append(request)
            self.assertEqual(20.0, timeout)
            return _Response()

        self.assertEqual(_VALID_PDF, download_pdf(SINGLES_ALPHA_PDF_URL, opener=opener))
        self.assertEqual("application/pdf", requests[0].get_header("Accept"))  # type: ignore[attr-defined]

        for invalid in (b"<html>challenge</html>", b"%PDF-1.7\nmissing eof"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(RankingSourceError, "ranking_source_schema_changed"):
                    download_pdf(SINGLES_ALPHA_PDF_URL, opener=lambda *_args, **_kwargs: _Response(invalid))

    def test_download_retries_rate_limit_with_bounded_retry_after(self) -> None:
        responses = iter(
            (
                _Response(status=429, headers={"Retry-After": "999"}),
                _Response(),
            )
        )
        sleeps: list[float] = []

        result = download_pdf(
            SINGLES_ALPHA_PDF_URL,
            opener=lambda *_args, **_kwargs: next(responses),
            sleeper=sleeps.append,
        )

        self.assertEqual(_VALID_PDF, result)
        self.assertEqual([30.0], sleeps)

    def test_oversized_content_length_is_rejected_without_reading(self) -> None:
        response = _Response(headers={"Content-Length": str(MAX_PDF_BYTES + 1)})

        with self.assertRaisesRegex(RankingSourceError, "ranking_source_coverage_truncated"):
            download_pdf(SINGLES_ALPHA_PDF_URL, opener=lambda *_args, **_kwargs: response)

        self.assertEqual([], response.read_sizes)

    def test_download_retries_timeout_with_bounded_backoff(self) -> None:
        attempts = 0
        sleeps: list[float] = []

        def opener(*_args: object, **_kwargs: object) -> _Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TimeoutError("never printed")
            return _Response()

        self.assertEqual(
            _VALID_PDF,
            download_pdf(SINGLES_ALPHA_PDF_URL, opener=opener, sleeper=sleeps.append),
        )
        self.assertEqual([1.0], sleeps)

    def test_redirect_to_any_other_host_or_path_is_blocked(self) -> None:
        response = _Response()
        response.geturl = lambda: "https://other.invalid/report.pdf"  # type: ignore[attr-defined]

        with self.assertRaisesRegex(RankingSourceError, "ranking_source_blocked"):
            download_pdf(SINGLES_ALPHA_PDF_URL, opener=lambda *_args, **_kwargs: response)


class AtpPdfSourceTests(unittest.TestCase):
    def test_mismatched_publication_dates_fail_before_raw_observation(self) -> None:
        reports = (
            ParsedRankingReport("singles", "2026-09-01", "Luka Bojicic Ono", 2101, 4),
            ParsedRankingReport("doubles", "2026-09-08", "Luka Bojicic Ono", 1784, 8),
        )
        with patch.object(AtpPdfRankingSource, "_report", side_effect=reports):
            with self.assertRaisesRegex(RankingSourceError, "ranking_source_incomplete"):
                AtpPdfRankingSource().fetch()


class AtpPdfProbeTests(unittest.TestCase):
    def test_probe_only_fetches_and_never_exposes_observation_or_persists(self) -> None:
        observation = RawRankingObservation(
            source="atp-pdf",
            atp_id="B0UF",
            name="Luka Bojicic Ono",
            ranking_date="2026-09-01",
            singles=RawDisciplineRanking(status="ranked", rank=2101, points=4),
            doubles=RawDisciplineRanking(status="ranked", rank=1784, points=8),
        )

        class Source:
            calls = 0

            def fetch(self) -> RawRankingObservation:
                self.calls += 1
                return observation

        source = Source()
        exit_code, lines = probe(source)  # type: ignore[arg-type]
        rendered = "\n".join(lines)

        self.assertEqual(0, exit_code)
        self.assertEqual(1, source.calls)
        self.assertNotIn(observation.name, rendered)
        self.assertNotIn(observation.ranking_date, rendered)
        self.assertTrue(rendered.endswith("decision=pending_manual_review"))
        self.assertIn("evidence_exact_name_match=true", rendered)
        self.assertNotIn("evidence_identity=true", rendered)
        self.assertIn("gate_identity=pending_manual_review", rendered)

    def test_probe_redacts_unexpected_failure_text(self) -> None:
        class BrokenSource:
            def fetch(self) -> RawRankingObservation:
                raise RuntimeError("https://private.example/?token=never-print")

        exit_code, lines = probe(BrokenSource())  # type: ignore[arg-type]
        rendered = "\n".join(lines)

        self.assertEqual(1, exit_code)
        self.assertIn("detail=ranking_source_incomplete", rendered)
        self.assertNotIn("private.example", rendered)
        self.assertNotIn("never-print", rendered)
        self.assertTrue(rendered.endswith("decision=no-go"))

    def test_probe_script_imports_when_invoked_like_the_workflow(self) -> None:
        root = Path(__file__).resolve().parents[2]
        completed = subprocess.run(
            [sys.executable, "scripts/probe_atp_pdfs.py", "--help"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()
