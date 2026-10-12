from __future__ import annotations

import json
import unittest
from datetime import datetime

from scripts.ranking_alerts.freshness import (
    DEFAULT_CALENDAR_PATH,
    CalendarError,
    FreshnessState,
    assess_publication,
    calendar_from_dict,
    load_calendar,
)


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.calendar = load_calendar()

    def assess(self, publication: str | None, instant: str):
        return assess_publication(publication, now=at(instant), calendar=self.calendar)

    def test_old_publication_is_stale_after_thursday_noon_brazil(self):
        result = self.assess("2026-09-28", "2026-10-08T15:00:00Z")
        self.assertEqual(FreshnessState.STALE, result.state)
        self.assertEqual("2026-10-05", result.expected_date)
        self.assertEqual("2026-10-08T15:00:00Z", result.cutoff)
        self.assertEqual(10, result.source_age_days)

    def test_cutoff_boundary_and_equivalent_timezones(self):
        self.assertEqual(FreshnessState.PENDING_PUBLICATION, self.assess("2026-09-28", "2026-10-08T14:59:59Z").state)
        utc = self.assess("2026-09-28", "2026-10-08T15:00:00Z")
        brazil = self.assess("2026-09-28", "2026-10-08T12:00:00-03:00")
        self.assertEqual(utc, brazil)

    def test_new_week_does_not_reset_previous_missed_sla(self):
        result = self.assess("2026-09-28", "2026-10-12T12:00:00Z")
        self.assertEqual(FreshnessState.STALE, result.state)
        self.assertEqual("2026-10-05", result.expected_date)
        self.assertEqual("2026-10-08T15:00:00Z", result.cutoff)
        self.assertEqual(FreshnessState.PENDING_PUBLICATION, self.assess("2026-10-05", "2026-10-12T12:00:00Z").state)

    def test_provider_regression_is_source_error_before_new_week_cutoff(self):
        result = assess_publication("2026-09-28", now=at("2026-10-12T12:00:00Z"), calendar=self.calendar, last_valid_date="2026-10-05")
        self.assertEqual(FreshnessState.SOURCE_ERROR, result.state)
        self.assertEqual("ranking_source_stale", result.reason)

    def test_current_edition_is_fresh_with_any_ranks(self):
        self.assertEqual(FreshnessState.FRESH, self.assess("2026-10-05", "2026-10-09T12:00:00Z").state)

    def test_future_nonedition_and_missing_dates_fail_closed(self):
        for value, reason in (("2026-10-12", "ranking_source_future"), ("2026-10-06", "ranking_source_edition_invalid"), (None, "ranking_source_schema_changed"), ("not a date", "ranking_source_schema_changed")):
            with self.subTest(value=value):
                result = self.assess(value, "2026-10-08T15:00:00Z")
                self.assertEqual(FreshnessState.SOURCE_ERROR, result.state)
                self.assertEqual(reason, result.reason)

    def test_official_exception_skips_no_edition_week(self):
        # Synthetic fixture for the exception mechanism, never shipped as an
        # alleged real ATP notice or used to manufacture a sporting snapshot.
        config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
        config["exceptions"] = [{"edition_date": "2026-10-05", "kind": "no_edition", "reference": "https://www.atptour.com/test-fixture-notice"}]
        calendar = calendar_from_dict(config)
        result = assess_publication("2026-09-28", now=at("2026-10-09T12:00:00Z"), calendar=calendar)
        self.assertEqual(FreshnessState.FRESH, result.state)
        self.assertEqual("2026-09-28", result.expected_date)
        rejected = assess_publication("2026-10-05", now=at("2026-10-09T12:00:00Z"), calendar=calendar)
        self.assertEqual(FreshnessState.SOURCE_ERROR, rejected.state)

    def test_moved_publication_uses_explicit_official_date(self):
        config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
        config["exceptions"] = [{"edition_date": "2026-10-05", "kind": "moved", "publication_date": "2026-10-06", "reference": "https://www.atptour.com/test-fixture-notice"}]
        calendar = calendar_from_dict(config)
        result = assess_publication("2026-10-06", now=at("2026-10-09T12:00:00Z"), calendar=calendar)
        self.assertEqual(FreshnessState.FRESH, result.state)

    def test_invalid_calendar_expiry_and_naive_clock_fail_closed(self):
        config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
        config["exceptions"] = [{"edition_date": "2026-10-05", "kind": "no_edition"}]
        with self.assertRaises(CalendarError):
            calendar_from_dict(config)
        with self.assertRaises(CalendarError):
            self.assess("2026-12-28", "2027-01-05T12:00:00Z")
        with self.assertRaises(CalendarError):
            self.assess("2026-10-05", "2026-10-06T12:00:00")


if __name__ == "__main__":
    unittest.main()
