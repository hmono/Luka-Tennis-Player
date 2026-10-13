from __future__ import annotations

import json
import unittest
from datetime import date, datetime

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

    def test_h2_inconclusive_october_12_keeps_expectation_and_exact_cutoff(self):
        config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
        self.assertEqual("inconclusive", config["review"]["edition_2026_10_12_status"])
        self.assertEqual([], config["exceptions"])
        self.assertEqual("inherited_not_recertified", config["review"]["horizon_status"])
        before = self.assess("2026-10-05", "2026-10-15T11:59:59-03:00")
        after = self.assess("2026-10-05", "2026-10-15T12:00:00-03:00")
        self.assertEqual(FreshnessState.PENDING_PUBLICATION, before.state)
        self.assertEqual(FreshnessState.STALE, after.state)
        self.assertEqual("2026-10-12", after.expected_date)
        self.assertEqual("2026-10-15T15:00:00Z", after.cutoff)

    def test_h2_synthetic_exception_changes_cutoff_without_manufacturing_observation(self):
        # Synthetic mechanics only: no official exception is asserted for 12/10.
        for kind in ("no_edition", "moved"):
            with self.subTest(kind=kind):
                config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
                exception = {"edition_date": "2026-10-12", "kind": kind,
                             "reference": "https://example.invalid/synthetic-notice"}
                if kind == "moved":
                    exception["publication_date"] = "2026-10-13"
                config["exceptions"] = [exception]
                calendar = calendar_from_dict(config)
                report = assess_publication("2026-10-05", now=at("2026-10-16T14:59:59Z"), calendar=calendar)
                self.assertEqual("2026-10-05", report.actual_date)
                self.assertEqual(FreshnessState.FRESH if kind == "no_edition" else FreshnessState.PENDING_PUBLICATION, report.state)
                if kind == "moved":
                    report = assess_publication("2026-10-05", now=at("2026-10-16T15:00:00Z"), calendar=calendar)
                    self.assertEqual(FreshnessState.STALE, report.state)
                    self.assertEqual("2026-10-13", report.expected_date)
                    self.assertEqual("2026-10-16T15:00:00Z", report.cutoff)

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

    def test_moved_publication_moves_internal_cutoff(self):
        config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
        config["exceptions"] = [{"edition_date": "2026-10-05", "kind": "moved", "publication_date": "2026-10-06", "reference": "https://example.com/synthetic-notice"}]
        calendar = calendar_from_dict(config)
        pending = assess_publication("2026-09-28", now=at("2026-10-09T14:59:59Z"), calendar=calendar)
        stale = assess_publication("2026-09-28", now=at("2026-10-09T15:00:00Z"), calendar=calendar)
        self.assertEqual(FreshnessState.PENDING_PUBLICATION, pending.state)
        self.assertEqual(FreshnessState.STALE, stale.state)
        self.assertEqual("2026-10-06", stale.expected_date)
        self.assertEqual("2026-10-09T15:00:00Z", stale.cutoff)

    def test_future_moved_date_is_not_expected_before_publication(self):
        config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
        config["exceptions"] = [{"edition_date": "2026-10-05", "kind": "moved", "publication_date": "2026-10-06", "reference": "https://example.com/synthetic-notice"}]
        calendar = calendar_from_dict(config)
        current = assess_publication("2026-09-28", now=at("2026-10-05T15:00:00Z"), calendar=calendar)
        future = assess_publication("2026-10-06", now=at("2026-10-05T15:00:00Z"), calendar=calendar)
        self.assertEqual(FreshnessState.FRESH, current.state)
        self.assertEqual("2026-09-28", current.expected_date)
        self.assertEqual(FreshnessState.SOURCE_ERROR, future.state)
        self.assertEqual("ranking_source_future", future.reason)

    def test_week_rolls_at_sao_paulo_midnight(self):
        sunday = self.assess("2026-10-05", "2026-10-12T02:59:59Z")
        monday = self.assess("2026-10-05", "2026-10-12T03:00:00Z")
        self.assertEqual(FreshnessState.FRESH, sunday.state)
        self.assertEqual("2026-10-05", sunday.expected_date)
        self.assertEqual(FreshnessState.PENDING_PUBLICATION, monday.state)
        self.assertEqual("2026-10-12", monday.expected_date)

    def test_production_horizon_is_blocked_and_expires_at_local_midnight(self):
        config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
        self.assertEqual("America/Sao_Paulo", config["cutoff"]["timezone"])
        self.assertEqual("2026-10-26", config["valid_until"])
        self.assertEqual("blocked_missing_official_edition_schedule", config["review"]["extension_status"])
        self.assertEqual(FreshnessState.FRESH, self.assess("2026-10-26", "2026-10-27T02:59:59Z").state)
        for instant in ("2026-10-27T03:00:00Z", "2026-11-05T15:00:00Z", "2026-12-31T15:00:00Z", "2027-01-01T15:00:00Z"):
            with self.subTest(instant=instant), self.assertRaises(CalendarError):
                self.assess("2026-10-26", instant)

    def test_validity_start_also_uses_local_date(self):
        with self.assertRaises(CalendarError):
            self.assess("2026-09-28", "2026-09-28T02:59:59Z")
        self.assertEqual(FreshnessState.FRESH, self.assess("2026-09-28", "2026-09-28T03:00:00Z").state)

    def test_synthetic_year_end_exceptions_and_expiry(self):
        # Tests the mechanism only; this does not authorize a production extension.
        config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
        config["valid_until"] = "2026-12-31"
        config["exceptions"] = [
            {"edition_date": day, "kind": "no_edition", "reference": "https://example.com/synthetic-notice"}
            for day in ("2026-12-21", "2026-12-28")
        ]
        calendar = calendar_from_dict(config)
        fresh = assess_publication("2026-12-14", now=at("2027-01-01T02:59:59Z"), calendar=calendar)
        self.assertEqual(FreshnessState.FRESH, fresh.state)
        self.assertEqual("2026-12-14", fresh.expected_date)
        invalid = assess_publication("2026-12-28", now=at("2026-12-31T15:00:00Z"), calendar=calendar)
        self.assertEqual("ranking_source_edition_invalid", invalid.reason)
        with self.assertRaises(CalendarError):
            assess_publication("2026-12-14", now=at("2027-01-01T03:00:00Z"), calendar=calendar)

    def test_future_end_of_reviewed_horizon_has_exact_internal_cutoff(self):
        self.assertEqual("2026-10-29T15:00:00+00:00", self.calendar.cutoff_for(date(2026, 10, 26)).isoformat())
        # The date arithmetic is valid, but no assessment after expiry is allowed.
        with self.assertRaises(CalendarError):
            self.assess("2026-10-19", "2026-10-29T15:00:00Z")

    def test_exception_validation_rejects_ambiguous_or_unreferenced_changes(self):
        base = {"edition_date": "2026-10-05", "kind": "moved", "publication_date": "2026-10-06", "reference": "https://example.com/synthetic-notice"}
        cases = [
            [{**base, "publication_date": "2026-10-12"}],  # another regular edition
            [{**base, "publication_date": "2026-10-27"}],  # outside review
            [{**base, "edition_date": "2026-10-06"}],
            [{**base, "edition_date": "2026-11-02"}],
            [{**base, "reference": ""}],
            [{**base, "kind": "unconfirmed"}],
            [base, base],
        ]
        for exceptions in cases:
            with self.subTest(exceptions=exceptions), self.assertRaises(CalendarError):
                config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
                config["exceptions"] = exceptions
                calendar_from_dict(config)

    def test_no_edition_without_prior_reviewed_publication_fails_closed(self):
        config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
        config["exceptions"] = [{"edition_date": "2026-09-28", "kind": "no_edition", "reference": "https://example.com/synthetic-notice"}]
        with self.assertRaises(CalendarError):
            assess_publication(None, now=at("2026-09-28T15:00:00Z"), calendar=calendar_from_dict(config))

    def test_invalid_calendar_expiry_and_naive_clock_fail_closed(self):
        config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
        config["exceptions"] = [{"edition_date": "2026-10-05", "kind": "no_edition"}]
        with self.assertRaises(CalendarError):
            calendar_from_dict(config)
        with self.assertRaises(CalendarError):
            self.assess("2026-12-28", "2027-01-05T12:00:00Z")
        with self.assertRaises(CalendarError):
            self.assess("2026-10-05", "2026-10-06T12:00:00")

    def test_calendar_version_rejects_boolean_and_float_schema(self):
        for version in (True, 1.0, "1"):
            with self.subTest(version=version):
                config = json.loads(DEFAULT_CALENDAR_PATH.read_text())
                config["schema_version"] = version
                with self.assertRaises(CalendarError):
                    calendar_from_dict(config)


if __name__ == "__main__":
    unittest.main()
