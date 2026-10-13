"""Calendar-free live collection and reversible source corrections."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS)) if str(SCRIPTS) not in sys.path else None

import update_rankings
from ranking_alerts.domain import (DisciplineRanking, DomainValidationError,
    RankingObservation, RankingsData, build_snapshot, rankings_from_dict, rankings_to_dict)
from ranking_alerts.freshness import FreshnessState, assess_observation
from ranking_alerts.itf_source import (ITF_BASE_URL, PROFILE_PATH, ItfOverviewResponse,
    ItfProfileCapture, ItfRankingSource)
from ranking_alerts.source import RankingSourceError
from ranking_alerts.storage import load_rankings, save_alert_state


def at(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def capture(edition="2026-10-05", *, doubles_edition=None, singles_rank=2250, title=None):
    def reply(discipline, day, rank):
        return ItfOverviewResponse(status=200, payload={"rankings": [{
            "name": f"ATP {discipline} Ranking", "rank": rank,
            "date": datetime.fromisoformat(day).strftime("%d %B %Y"),
        }]}, retrieved_at="2026-12-02T12:00:00Z")
    return ItfProfileCapture(
        page_title=title or "Luka Bojicic Ono Tennis Player Profile | ITF",
        final_url=ITF_BASE_URL + PROFILE_PATH, navigation_status=200,
        dom_identity="Luka Bojicic Ono Men's Singles Overview",
        singles=reply("Singles", edition, singles_rank),
        doubles=reply("Doubles", doubles_edition or edition, 1417),
    )


class PublicationDrivenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.rankings = Path(self.temp.name) / "rankings.json"
        self.state = Path(self.temp.name) / "alerts.json"

    def collect(self, value, instant):
        return update_rankings.collect(
            source=ItfRankingSource(capture=lambda timeout: value),
            rankings_path=self.rankings, state_path=self.state,
            clock=lambda: at(instant),
        )

    def test_eight_weeks_without_edition_then_delayed_equal_ranks(self):
        with patch.object(update_rankings, "load_calendar", side_effect=AssertionError("calendar accessed")):
            first = self.collect(capture(), "2026-10-06T12:00:00Z")
            before = self.rankings.read_bytes(), self.state.read_bytes()
            for days in range(1, 57):
                instant = (at("2026-10-06T12:00:00Z") + timedelta(days=days)).isoformat()
                repeated = self.collect(capture(), instant)
                self.assertEqual(FreshnessState.NO_NEW_EDITION_OBSERVED, repeated.freshness.state)
                self.assertEqual("unchanged", repeated.snapshot_status)
                self.assertEqual("none", repeated.outbox_status)
            self.assertEqual(before, (self.rankings.read_bytes(), self.state.read_bytes()))
            # A Tuesday source publication is accepted without editing any calendar.
            new = self.collect(capture("2026-12-01"), "2026-12-02T12:00:00Z")
            self.assertEqual(FreshnessState.FRESH, new.freshness.state)
            self.assertEqual(2, len(new.rankings.snapshots))
            self.assertEqual(2, len(new.state.outbox))
            self.assertEqual("weekly_digest", new.state.outbox[-1].event_type)
            message = update_rankings._message_for_snapshot(new.rankings, new.snapshot, "weekly_digest")
            self.assertIn("sem alteração", message)
            self.assertNotIn("pts", message)
            self.assertIsNone(first.snapshot.singles.points)
            again = self.collect(capture("2026-12-01"), "2026-12-03T12:00:00Z")
            self.assertEqual(2, len(again.state.outbox))

    def test_inconsistent_disciplines_and_identity_recover_without_mutating_facts(self):
        first = self.collect(capture(), "2026-10-06T12:00:00Z")
        before = self.rankings.read_bytes(), self.state.read_bytes()
        for broken in (capture("2026-10-13", doubles_edition="2026-10-05"),
                       capture("2026-10-13", title="Luka Bojicic Ono Junior Tennis Player Profile | ITF")):
            with self.assertRaises(RankingSourceError) as error:
                self.collect(broken, "2026-10-14T12:00:00Z")
            self.assertEqual(FreshnessState.SOURCE_ERROR, error.exception.freshness.state)
            self.assertEqual(before, (self.rankings.read_bytes(), self.state.read_bytes()))
        recovered = self.collect(capture("2026-10-13"), "2026-10-14T12:00:00Z")
        self.assertEqual(FreshnessState.FRESH, recovered.freshness.state)
        self.assertEqual(first.rankings.snapshots, recovered.rankings.snapshots[:1])
        provenance = recovered.source_telemetry
        self.assertEqual("B0UF", provenance["atp_id"])
        self.assertEqual("800625103", provenance["itf_player_id"])
        for discipline in ("singles", "doubles"):
            self.assertEqual("2026-10-13", provenance[discipline]["ranking_date"])

    def test_a_b_a_b_corrections_are_chained_append_only_and_recompute_highs(self):
        outcomes = []
        for hour, rank in enumerate((1700, 2250, 1700, 2250), start=12):
            outcome = self.collect(capture(singles_rank=rank), f"2026-10-06T{hour}:00:00Z")
            if outcomes:
                previous = outcomes[-1]
                self.assertEqual(previous.rankings.snapshots, outcome.rankings.snapshots[:-1])
                self.assertEqual(previous.snapshot.id, outcome.snapshot.source_revision_of)
                self.assertEqual(FreshnessState.NO_NEW_EDITION_OBSERVED, outcome.freshness.state)
                self.assertEqual("revised", outcome.snapshot_status)
            self.assertEqual(min(rank, 1827), outcome.snapshot.singles.career_high_rank)
            outcomes.append(outcome)
        latest = outcomes[-1]
        self.assertEqual(4, len({item.id for item in latest.rankings.snapshots}))
        self.assertEqual(4, len(latest.state.outbox))
        self.assertEqual(1, sum(update_rankings._sendable(item) for item in latest.state.outbox))
        self.assertEqual(latest.rankings, load_rankings(self.rankings))
        again = self.collect(capture(singles_rank=2250), "2026-10-06T16:00:00Z")
        self.assertEqual("unchanged", again.snapshot_status)
        self.assertEqual(4, len(again.rankings.snapshots))

    def test_cli_default_uses_publication_mode_without_calendar(self):
        source = ItfRankingSource(capture=lambda timeout: capture())
        with patch.object(update_rankings, "_selected_source", return_value=source), \
             patch.object(update_rankings, "load_calendar", side_effect=AssertionError("calendar accessed")), \
             redirect_stdout(StringIO()) as output:
            code = update_rankings.main(["dry-run", "--source", "itf", "--rankings-path", str(self.rankings),
                                         "--state-path", str(self.state)], clock=lambda: at("2027-01-05T12:00:00Z"))
        self.assertEqual(0, code, output.getvalue())
        self.assertFalse(self.rankings.exists())

    def test_reverted_pending_correction_cannot_send_withdrawn_facts(self):
        first = self.collect(capture(), "2026-10-06T12:00:00Z")
        receipt = replace(first.state.outbox[0], status="sent", sent_at="2026-10-06T12:01:00Z",
                          delivery_status="provider_accepted")
        save_alert_state(self.state, replace(first.state, outbox=(receipt,)), first.rankings)
        changed = self.collect(capture(singles_rank=2240), "2026-10-06T13:00:00Z")
        reverted = self.collect(capture(), "2026-10-06T14:00:00Z")
        self.assertEqual(receipt, reverted.state.outbox[0])
        self.assertEqual("ranking_correction", reverted.state.outbox[-1].event_type)
        self.assertEqual(reverted.state.outbox[-1].id, reverted.state.outbox[-2].superseded_by)
        self.assertFalse(update_rankings._sendable(reverted.state.outbox[-2]))
        self.assertEqual(changed.rankings.snapshots, reverted.rankings.snapshots[:-1])
        repeated = self.collect(capture(), "2026-10-06T15:00:00Z")
        self.assertEqual(reverted.state.outbox, repeated.state.outbox)


class PublicationAssessmentTests(unittest.TestCase):
    def test_old_repeat_has_no_calendar_expiry_or_atp_stale_claim(self):
        report = assess_observation("2026-10-05", last_valid_date="2026-10-05", now=at("2027-03-09T12:00:00Z"))
        self.assertEqual(FreshnessState.NO_NEW_EDITION_OBSERVED, report.state)
        self.assertIsNone(report.reason)
        self.assertEqual("publication-driven-v1", report.calendar_version)
        self.assertEqual(155, report.source_age_days)

    def test_future_and_regression_blocked_but_off_monday_advance_is_valid(self):
        for edition, reason in (("2026-10-15", "ranking_source_future"),
                                ("2026-09-28", "ranking_source_stale"),
                                ("bad", "ranking_source_schema_changed")):
            report = assess_observation(edition, last_valid_date="2026-10-05", now=at("2026-10-14T12:00:00Z"))
            self.assertEqual(FreshnessState.SOURCE_ERROR, report.state)
            self.assertEqual(reason, report.reason)
        report = assess_observation("2026-10-13", last_valid_date="2026-10-05", now=at("2026-10-14T12:00:00Z"))
        self.assertEqual(FreshnessState.FRESH, report.state)

    def test_revision_provenance_cannot_be_missing_cross_edition_or_forward(self):
        observation = RankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
            ranking_date="2026-10-05", singles=DisciplineRanking(rank=2250, points=None),
            doubles=DisciplineRanking(rank=1417, points=None))
        first = build_snapshot(observation, "2026-10-06T12:00:00Z")
        revision = build_snapshot(replace(observation, singles=DisciplineRanking(rank=2240, points=None)),
            "2026-10-06T13:00:00Z", source_revision_of=first.id, chain_revision=True)
        valid = RankingsData(snapshots=(first, revision))
        self.assertEqual(valid, rankings_from_dict(rankings_to_dict(valid)))
        # Historical content-addressed revisions retain their IDs on load.
        legacy = build_snapshot(replace(observation, singles=DisciplineRanking(rank=2240, points=None)),
            "2026-10-06T13:00:00Z", source_revision_of=first.id)
        legacy_history = RankingsData(snapshots=(first, legacy))
        self.assertEqual(legacy_history, rankings_from_dict(rankings_to_dict(legacy_history)))
        for snapshots in ((revision,),
                          (first, replace(revision, captured_at="2026-10-06T11:00:00Z")),
                          (first, replace(revision, ranking_date="2026-10-12")),
                          (first, replace(revision, source_revision_of=revision.id))):
            with self.subTest(snapshots=snapshots), self.assertRaises(DomainValidationError):
                RankingsData(snapshots=tuple(sorted(snapshots, key=lambda item: (item.ranking_date, item.captured_at, item.id))))
        later = build_snapshot(replace(observation, singles=DisciplineRanking(rank=2230, points=None)),
            "2026-10-06T14:00:00Z", source_revision_of=first.id, chain_revision=True)
        with self.assertRaisesRegex(DomainValidationError, "invalid_revision_reference"):
            RankingsData(snapshots=(first, revision, later))


if __name__ == "__main__":
    unittest.main()
