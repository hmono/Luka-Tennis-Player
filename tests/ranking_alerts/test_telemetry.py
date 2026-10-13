from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts.ranking_alerts.freshness import FreshnessState, assess_publication, load_calendar
from scripts.ranking_alerts.telemetry import emit_collection_summary, emit_schedule_summary, schedule_timing


def at(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class TelemetryTests(unittest.TestCase):
    def test_thursday_check_runs_just_after_publication_cutoff(self):
        report = schedule_timing(event="schedule", created_at=at("2026-10-15T15:06:00Z"), started_at=at("2026-10-15T15:08:00Z"))
        self.assertEqual("2026-10-15T15:05:00Z", report.expected_at)
        self.assertEqual(3, report.delay_minutes)

    def test_delayed_schedule_includes_creation_and_queue_delay(self):
        report = schedule_timing(event="schedule", created_at=at("2026-10-13T12:20:00Z"), started_at=at("2026-10-13T18:39:00Z"))
        self.assertEqual("2026-10-13T12:00:00Z", report.expected_at)
        self.assertEqual(399, report.delay_minutes)
        self.assertTrue(report.delayed_over_60_minutes)

    def test_sixty_minute_boundary_and_manual_run(self):
        report = schedule_timing(event="schedule", created_at=at("2026-10-14T12:01:00Z"), started_at=at("2026-10-14T13:00:00Z"))
        self.assertFalse(report.delayed_over_60_minutes)
        manual = schedule_timing(event="workflow_dispatch", created_at=at("2026-10-14T18:00:00Z"), started_at=at("2026-10-14T18:01:00Z"))
        self.assertIsNone(manual.expected_at)
        self.assertIsNone(manual.delay_minutes)

    def test_timezone_equivalence_and_delayed_run_crossing_midnight(self):
        report = schedule_timing(event="schedule", created_at=at("2026-10-14T03:00:00Z"), started_at=at("2026-10-14T04:00:00Z"))
        self.assertEqual("2026-10-13T12:00:00Z", report.expected_at)
        brazil = schedule_timing(event="schedule", created_at=at("2026-10-14T00:00:00-03:00"), started_at=at("2026-10-14T01:00:00-03:00"))
        self.assertEqual(report, brazil)

    def test_summary_separates_schedule_delay_from_pending_publication(self):
        assessment = assess_publication("2026-10-05", now=at("2026-10-14T12:00:00Z"), calendar=load_calendar())
        self.assertEqual(FreshnessState.PENDING_PUBLICATION, assessment.state)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.md"
            report = schedule_timing(event="schedule", created_at=at("2026-10-14T12:10:00Z"), started_at=at("2026-10-14T13:01:00Z"))
            with redirect_stdout(StringIO()):
                emit_schedule_summary(report, source_age_days=9, path=path)
                emit_collection_summary(assessment, path=path, source_telemetry={"source": "itf", "source_ranking_date": "2026-10-05", "apikey": "secret", "body": "private"})
            text = path.read_text()
            self.assertIn("DELAY >60 minutes", text)
            self.assertIn("PENDING_PUBLICATION", text)
            self.assertIn("no publication SLA violation", text)
            self.assertIn("Source age: 9 days", text)
            self.assertNotIn("secret", text)
            self.assertNotIn("private", text)

    def test_source_error_summary_keeps_sanitized_acquisition_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.md"
            stream = StringIO()
            with redirect_stdout(stream):
                emit_collection_summary(None, error_code="ranking_source_blocked", source_telemetry={"source": "itf", "navigation_status": 403, "singles": {"http_status": 403, "body": "private"}}, path=path)
            self.assertIn("SOURCE_ERROR", path.read_text())
            self.assertIn("403", path.read_text())
            self.assertNotIn("private", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
