from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import update_rankings
from ranking_alerts.domain import DisciplineRanking, RankingObservation, RankingsData, build_snapshot
from ranking_alerts.incidents import load_incidents, pending_incidents
from ranking_alerts.providers import DeliveryError, DeliveryReceipt
from ranking_alerts.source import RawDisciplineRanking, RawRankingObservation, RankingSourceError
from ranking_alerts.storage import load_alert_state, load_rankings, save_rankings


class Source:
    name = "itf"

    def __init__(self, edition="2026-09-28", error=None):
        self.edition, self.error = edition, error

    def fetch(self):
        if self.error:
            raise RankingSourceError(self.error)
        return RawRankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
            ranking_date=self.edition,
            singles=RawDisciplineRanking(status="ranked", rank=2250, points=None),
            doubles=RawDisciplineRanking(status="ranked", rank=1417, points=None))


class MockProvider:
    name = "callmebot"
    last_attempt_count = 1

    def __init__(self):
        self.messages = []
        self.accepted_at = "2026-10-08T15:01:00Z"

    def send(self, *, message, event_id):
        self.messages.append((message, event_id))
        return DeliveryReceipt(provider=self.name, accepted_at=self.accepted_at, http_status=200)


class SprintIntegrationTests(unittest.TestCase):
    def test_h2_revision_retracts_high_without_rewriting_history_or_receipts(self):
        class RevisedSource(Source):
            def __init__(self, edition, singles, doubles):
                self.edition, self.singles, self.doubles = edition, singles, doubles

            def fetch(self):
                return RawRankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
                    ranking_date=self.edition,
                    singles=RawDisciplineRanking(status="ranked", rank=self.singles, points=None),
                    doubles=RawDisciplineRanking(status="ranked", rank=self.doubles, points=None))

        self.assertEqual(0, self.main("collect", "2026-10-13T12:00:00Z",
            RevisedSource("2026-10-12", 1700, 1300))[0])
        initial = load_rankings(self.rankings).snapshots[-1]
        self.provider.accepted_at = "2026-10-13T12:01:00Z"
        self.assertEqual(0, self.main("deliver", "2026-10-13T12:01:00Z",
            enabled=True, edition_date="2026-10-12")[0])
        receipt = load_alert_state(self.state, load_rankings(self.rankings)).outbox[-1]
        corrected_source = RevisedSource("2026-10-12", 1900, 1500)
        self.assertEqual(0, self.main("collect", "2026-10-13T12:02:00Z", corrected_source)[0])
        rankings = load_rankings(self.rankings)
        correction = rankings.snapshots[-1]
        self.assertEqual(initial, rankings.snapshots[-2])
        self.assertEqual(initial.id, correction.source_revision_of)
        self.assertEqual((1827, 1407), (correction.singles.career_high_rank, correction.doubles.career_high_rank))
        self.assertEqual(receipt, load_alert_state(self.state, rankings).outbox[0])
        self.provider.accepted_at = "2026-10-13T12:03:00Z"
        self.assertEqual(0, self.main("deliver", "2026-10-13T12:03:00Z",
            enabled=True, edition_date="2026-10-12")[0])
        message = self.provider.messages[-1][0]
        self.assertIn("Correção ATP Ranking — 2026-10-12", message)
        self.assertIn("CH #1.827 (2025-12-01)", message)
        self.assertIn("CH #1.407 (2026-06-22)", message)
        before = self.rankings.read_bytes(), self.state.read_bytes()
        self.assertEqual(0, self.main("collect", "2026-10-13T12:04:00Z", corrected_source)[0])
        self.assertEqual(before, (self.rankings.read_bytes(), self.state.read_bytes()))
        self.assertEqual(0, self.main("collect", "2026-10-20T12:00:00Z",
            RevisedSource("2026-10-19", 1800, 1350))[0])
        rankings = load_rankings(self.rankings)
        current = rankings.snapshots[-1]
        self.assertEqual((1800, 1350), (current.singles.career_high_rank, current.doubles.career_high_rank))
        self.assertIn("Novo career high: Singles #1.800, Doubles #1.350",
            update_rankings._message_for_snapshot(rankings, current, "ranking_change"))
        self.assertEqual(receipt, load_alert_state(self.state, rankings).outbox[0])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.rankings, self.state, self.incidents = root / "rankings.json", root / "state.json", root / "incidents.json"
        observation = RankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
            ranking_date="2026-09-28",
            singles=DisciplineRanking(rank=2250, points=None, career_high_rank=1827, career_high_date="2025-12-01"),
            doubles=DisciplineRanking(rank=1417, points=None, career_high_rank=1407, career_high_date="2026-06-22"))
        save_rankings(self.rankings, RankingsData(snapshots=(build_snapshot(observation, "2026-09-29T12:00:00Z"),)))
        self.state.write_text('{"schema_version":1,"outbox":[]}\n')
        self.original_rankings, self.original_state = self.rankings.read_bytes(), self.state.read_bytes()
        self.provider = MockProvider()

    def main(self, command, instant, source=Source(), enabled=False, incidents_only=False,
             edition_date="2026-10-05", clock=None, checkpoint=None):
        args = [command, "--provider" if command == "deliver" else "--source", "callmebot" if command == "deliver" else "itf",
                "--rankings-path", str(self.rankings), "--state-path", str(self.state), "--incidents-path", str(self.incidents)]
        # This suite preserves the pre-autonomy calendar and legacy sender
        # contract explicitly. Publication-driven behavior has its own suite.
        if command in {"collect", "dry-run"}:
            args.extend(("--calendar-path", str(update_rankings.DEFAULT_CALENDAR_PATH)))
        if incidents_only:
            args.append("--incidents-only")
        if command == "deliver" and edition_date is not None:
            args.extend(("--edition-date", edition_date))
        output, errors = StringIO(), StringIO()
        with patch.object(update_rankings, "_selected_source", return_value=source), \
             patch.object(update_rankings.CallMeBotProvider, "from_env", return_value=self.provider) as factory, \
             patch.dict("os.environ", {"ATP_RANKING_DELIVERY_ENABLED": "true" if enabled else "false"}), \
             redirect_stdout(output), redirect_stderr(errors):
            result = update_rankings.main(args, clock=clock or (lambda: datetime.fromisoformat(instant.replace("Z", "+00:00"))),
                                          checkpoint=checkpoint or (lambda: None))
        return result, output.getvalue(), errors.getvalue(), factory.call_count

    def test_h2_fresh_edition_does_not_release_older_pending_digest(self):
        # Synthetic observations test delivery selection, not actual ATP publication.
        code, output, _, calls = self.main("collect", "2026-10-13T12:00:00Z", Source("2026-10-05"))
        self.assertEqual(0, code)
        self.assertIn("PENDING_PUBLICATION", output)
        self.assertEqual(0, calls)
        older = load_alert_state(self.state, load_rankings(self.rankings)).outbox[0]
        self.assertIsNone(load_rankings(self.rankings).snapshots[-1].singles.points)
        self.assertIsNone(load_rankings(self.rankings).snapshots[-1].doubles.points)
        self.assertEqual("2026-10-05", load_rankings(self.rankings).snapshots[-1].ranking_date)
        self.assertEqual(0, self.main("collect", "2026-10-13T12:01:00Z", Source("2026-10-12"))[0])
        self.provider.accepted_at = "2026-10-13T12:02:00Z"
        code, output, errors, _ = self.main("deliver", "2026-10-13T12:02:00Z", enabled=True, edition_date="2026-10-12")
        self.assertEqual(1, code)  # Held older intention remains visible for review.
        self.assertIn("sporting_edition_held=1", output)
        self.assertIn("ranking_delivery_review_required", errors)
        self.assertEqual(1, len(self.provider.messages))
        self.assertIn("ATP Ranking — 2026-10-12", self.provider.messages[0][0])
        self.assertEqual(older, load_alert_state(self.state, load_rankings(self.rankings)).outbox[0])
        before = (self.rankings.read_bytes(), self.state.read_bytes())
        code, _, _, calls = self.main("deliver", "2026-10-13T12:03:00Z", enabled=True, edition_date="2026-10-12")
        self.assertEqual((1, 0, 1), (code, calls, len(self.provider.messages)))
        self.assertEqual(before, (self.rankings.read_bytes(), self.state.read_bytes()))

    def test_h2_sporting_delivery_requires_confirmed_current_edition(self):
        self.assertEqual(0, self.main("collect", "2026-10-06T12:00:00Z", Source("2026-10-05"))[0])
        before = (self.rankings.read_bytes(), self.state.read_bytes())
        for edition, instant, error in (
            (None, "2026-10-06T12:01:00Z", "ranking_delivery_edition_required"),
            ("2026-10-05", "2026-10-13T12:01:00Z", "ranking_delivery_edition_not_fresh"),
            ("2026-10-12", "2026-10-13T12:01:00Z", "ranking_delivery_edition_not_fresh"),
            ("not-a-date", "2026-10-06T12:01:00Z", "ranking_delivery_edition_not_fresh"),
        ):
            with self.subTest(edition=edition, instant=instant):
                code, _, errors, calls = self.main("deliver", instant, enabled=True, edition_date=edition)
                self.assertEqual((1, 0), (code, calls))
                self.assertIn(error, errors)
                self.assertEqual(before, (self.rankings.read_bytes(), self.state.read_bytes()))
        self.assertEqual([], self.provider.messages)

    def test_h2_expired_calendar_blocks_delivery_of_last_configured_edition(self):
        self.assertEqual(0, self.main("collect", "2026-10-26T12:00:00Z", Source("2026-10-26"))[0])
        before = self.state.read_bytes()
        code, _, errors, calls = self.main("deliver", "2026-10-27T03:00:00Z", enabled=True, edition_date="2026-10-26")
        self.assertEqual((1, 0), (code, calls))
        self.assertIn("ranking_calendar_invalid", errors)
        self.assertEqual(before, self.state.read_bytes())

    def test_h2_slow_checkpoint_crossing_local_monday_never_calls_provider(self):
        self.assertEqual(0, self.main("collect", "2026-10-18T12:00:00Z", Source("2026-10-12"))[0])
        current = [datetime.fromisoformat("2026-10-19T02:59:59+00:00")]
        def checkpoint():
            current[0] = datetime.fromisoformat("2026-10-19T03:00:00+00:00")
        code, _, errors, _ = self.main("deliver", "2026-10-19T02:59:59Z", enabled=True,
            edition_date="2026-10-12", clock=lambda: current[0], checkpoint=checkpoint)
        self.assertEqual(1, code)
        self.assertIn("ranking_delivery_edition_not_fresh", errors)
        self.assertEqual([], self.provider.messages)
        item = load_alert_state(self.state, load_rankings(self.rankings)).outbox[-1]
        self.assertFalse(item.retryable)
        self.assertIsNotNone(item.attempt_id)

    def test_h2_source_recovery_keeps_uncertain_incident_delivery_visible(self):
        self.assertEqual(1, self.main("collect", "2026-10-06T12:00:00Z", Source(error="ranking_source_timeout"))[0])
        with patch.object(self.provider, "send", side_effect=DeliveryError("transport_timeout", 1)):
            self.assertEqual(1, self.main("deliver", "2026-10-06T12:01:00Z", enabled=True, incidents_only=True)[0])
        uncertain = load_incidents(self.incidents)
        self.assertEqual(0, self.main("collect", "2026-10-09T12:00:00Z", Source("2026-10-05"))[0])
        recovered = load_incidents(self.incidents)
        self.assertEqual(uncertain.events, recovered.events[:-1])
        self.assertEqual("recovered", recovered.events[-1]["kind"])
        before = self.incidents.read_bytes()
        code, output, errors, calls = self.main("deliver", "2026-10-09T12:01:00Z", enabled=True, incidents_only=True)
        self.assertEqual((1, 0), (code, calls))
        self.assertIn("delivery_review_required=1", output)
        self.assertIn("ranking_delivery_review_required", errors)
        self.assertEqual(before, self.incidents.read_bytes())

    def test_h2_operational_429_cannot_retry_across_week_or_calendar_expiry(self):
        class Reply:
            status = 429
            headers = {"Retry-After": "120"}
            def close(self):
                pass
        for edition, instant, error in (
            ("2026-10-12", "2026-10-19T02:59:59+00:00", "ranking_delivery_edition_not_fresh"),
            ("2026-10-26", "2026-10-27T02:59:59+00:00", "ranking_calendar_invalid"),
        ):
            with self.subTest(edition=edition):
                self.setUp()
                self.assertEqual(0, self.main("collect", instant, Source(edition))[0])
                current = [datetime.fromisoformat(instant)]
                requests, sleeps = [], []
                def opener(request, **kwargs):
                    requests.append(current[0])
                    return Reply()
                def factory(**kwargs):
                    return update_rankings.CallMeBotProvider(phone="+5511999999999", api_key="test-only",
                        opener=opener, sleep=sleeps.append, now=lambda: current[0], **kwargs)
                args = ["deliver", "--provider", "callmebot", "--edition-date", edition,
                        "--rankings-path", str(self.rankings), "--state-path", str(self.state),
                        "--incidents-path", str(self.incidents)]
                with patch.object(update_rankings.CallMeBotProvider, "from_env", side_effect=factory) as configured, \
                     patch.dict("os.environ", {"ATP_RANKING_DELIVERY_ENABLED": "true"}), \
                     redirect_stdout(StringIO()), redirect_stderr(StringIO()) as errors:
                    self.assertEqual(1, update_rankings.main(args, clock=lambda: current[0], checkpoint=lambda: None))
                    self.assertIn("http_429", errors.getvalue())
                    item = load_alert_state(self.state, load_rankings(self.rankings)).outbox[-1]
                    self.assertEqual(("pending", 1, True), (item.status, item.attempts, item.retryable))
                    self.assertIsNotNone(item.attempt_id)
                    before = self.state.read_bytes()
                    current[0] += timedelta(seconds=120)
                    self.assertEqual(1, update_rankings.main(args, clock=lambda: current[0], checkpoint=lambda: None))
                    self.assertIn(error, errors.getvalue())
                    self.assertEqual(before, self.state.read_bytes())
                    configured.assert_called_once_with(max_attempts=1)
                self.assertEqual(1, len(requests))
                self.assertEqual([], sleeps)

    def test_h2_429_retry_in_later_current_run_reserves_new_attempt_and_deduplicates(self):
        self.assertEqual(0, self.main("collect", "2026-10-13T12:00:00Z", Source("2026-10-12"))[0])
        requests, checkpoints = [], []
        class Reply:
            headers = {}
            def __init__(self, status):
                self.status = status
            def close(self):
                pass
            def read(self, limit):
                return b"Message queued."
        def checkpoint():
            item = load_alert_state(self.state, load_rankings(self.rankings)).outbox[-1]
            checkpoints.append((item.attempt_id, item.retryable))
        def opener(request, **kwargs):
            item = load_alert_state(self.state, load_rankings(self.rankings)).outbox[-1]
            self.assertEqual((item.attempt_id, False), checkpoints[-1])
            requests.append(item.attempt_id)
            return Reply(429 if len(requests) == 1 else 200)
        def factory(**kwargs):
            return update_rankings.CallMeBotProvider(phone="+5511999999999", api_key="test-only",
                opener=opener, sleep=lambda seconds: self.fail("no internal retry"),
                now=lambda: datetime.fromisoformat("2026-10-13T12:01:00+00:00"), **kwargs)
        args = ["deliver", "--provider", "callmebot", "--edition-date", "2026-10-12",
                "--rankings-path", str(self.rankings), "--state-path", str(self.state),
                "--incidents-path", str(self.incidents)]
        with patch.object(update_rankings.CallMeBotProvider, "from_env", side_effect=factory), \
             patch.dict("os.environ", {"ATP_RANKING_DELIVERY_ENABLED": "true"}), \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            for expected in (1, 0, 0):
                self.assertEqual(expected, update_rankings.main(args,
                    clock=lambda: datetime.fromisoformat("2026-10-13T12:01:00+00:00"), checkpoint=checkpoint))
        self.assertEqual(2, len(set(requests)))
        item = load_alert_state(self.state, load_rankings(self.rankings)).outbox[-1]
        self.assertEqual(("sent", 2, False), (item.status, item.attempts, item.retryable))

    def test_failed_collection_delivers_only_incident_and_preserves_sporting_intention(self):
        self.assertEqual(0, self.main("collect", "2026-10-06T12:00:00Z", Source("2026-10-05"))[0])
        self.assertEqual(1, self.main("collect", "2026-10-06T12:01:00Z", Source(error="ranking_source_timeout"))[0])
        before = self.state.read_bytes()
        code, _, _, _ = self.main("deliver", "2026-10-08T15:01:00Z", enabled=True, incidents_only=True)
        self.assertEqual(0, code)
        self.assertEqual(before, self.state.read_bytes())
        self.assertEqual(1, len(self.provider.messages))
        self.assertIn("SOURCE_ERROR", self.provider.messages[0][0])

    def test_collection_output_allows_sporting_delivery_only_for_fresh_qualified_edition(self):
        for source, instant, expected in ((Source("2026-10-05"), "2026-10-06T12:00:00Z", "true"),
                (Source(), "2026-10-06T12:00:00Z", "false"),
                (Source(), "2026-10-08T15:00:00Z", "false"),
                (Source(error="ranking_source_timeout"), "2026-10-06T12:00:00Z", "false"),
                (Source("2026-10-26"), "2026-10-27T12:00:00Z", "false")):
            with self.subTest(instant=instant, expected=expected):
                self.setUp()
                path = self.state.with_name("actions-output.txt")
                with patch.dict("os.environ", {"GITHUB_OUTPUT": str(path)}):
                    self.main("collect", instant, source)
                self.assertIn(f"sporting_delivery_allowed={expected}", path.read_text())
                self.assertIn(f"sporting_edition_date={'2026-10-05' if expected == 'true' else ''}\n", path.read_text())

    def test_quarantined_attempt_is_visible_as_failure_on_next_cli_run(self):
        from ranking_alerts.providers import DeliveryError
        self.assertEqual(0, self.main("collect", "2026-10-06T12:00:00Z", Source("2026-10-05"))[0])
        with patch.object(self.provider, "send", side_effect=DeliveryError("transport_timeout", 1)):
            self.assertEqual(1, self.main("deliver", "2026-10-08T15:01:00Z", enabled=True)[0])
        code, output, errors, factories = self.main("deliver", "2026-10-09T12:00:00Z", enabled=True)
        self.assertEqual(1, code)
        self.assertIn("delivery_review_required=1", output)
        self.assertIn("ranking_delivery_review_required", errors)
        self.assertEqual(0, factories)

    def test_stale_dry_run_has_no_persistence_or_provider_construction(self):
        code, output, errors, calls = self.main("dry-run", "2026-10-08T15:00:00Z")
        self.assertEqual(0, code)
        self.assertIn("incident=would_create", output)
        self.assertEqual(0, calls)
        self.assertFalse(self.incidents.exists())
        self.assertEqual(self.original_rankings, self.rankings.read_bytes())
        self.assertEqual(self.original_state, self.state.read_bytes())

    def test_boundary_multiple_crons_and_stale_recovery_generate_one_intention_each(self):
        self.assertEqual(0, self.main("collect", "2026-10-08T14:59:59Z")[0])
        self.assertFalse(self.incidents.exists())
        self.assertEqual(0, self.main("collect", "2026-10-08T15:00:00Z")[0])
        ledger_bytes = self.incidents.read_bytes()
        self.assertEqual(0, self.main("collect", "2026-10-09T12:00:00Z")[0])
        self.assertEqual(ledger_bytes, self.incidents.read_bytes())
        self.assertEqual(self.original_rankings, self.rankings.read_bytes())
        self.assertEqual(self.original_state, self.state.read_bytes())
        self.assertEqual(0, self.main("deliver", "2026-10-08T15:01:00Z", enabled=True)[0])
        self.assertEqual(0, self.main("deliver", "2026-10-09T12:00:00Z", enabled=True)[0])
        self.assertEqual(1, len(self.provider.messages))
        self.assertIn("RANKING_STALE", self.provider.messages[0][0])
        self.assertEqual(0, self.main("collect", "2026-10-09T12:00:00Z", Source("2026-10-05"))[0])
        self.assertEqual("recovered", load_incidents(self.incidents).events[-1]["kind"])
        self.assertEqual("2026-10-05", load_incidents(self.incidents).events[-1]["recovery_date"])
        self.provider.accepted_at = "2026-10-09T12:01:00Z"
        self.assertEqual(0, self.main("deliver", "2026-10-09T12:01:00Z", enabled=True)[0])
        self.assertEqual(0, self.main("collect", "2026-10-09T12:02:00Z", Source("2026-10-05"))[0])
        self.assertEqual(0, self.main("deliver", "2026-10-09T12:03:00Z", enabled=True)[0])
        self.assertEqual(2, len(self.provider.messages))
        self.assertIn("ATP Ranking — 2026-10-05", self.provider.messages[1][0])
        self.assertEqual((), pending_incidents(load_incidents(self.incidents)))

    def test_source_error_persists_independent_incident_without_changing_valid_state(self):
        code, _, error, calls = self.main("collect", "2026-10-08T15:00:00Z", Source(error="ranking_source_blocked"))
        self.assertEqual(1, code)
        self.assertIn("error=ranking_source_blocked", error)
        self.assertEqual(0, calls)
        ledger = load_incidents(self.incidents)
        self.assertEqual("ranking_source_error:http:2026-10-05", ledger.events[0]["incident_id"])
        before = self.incidents.read_bytes()
        self.assertEqual(1, self.main("collect", "2026-10-09T12:00:00Z", Source(error="ranking_source_blocked"))[0])
        self.assertEqual(before, self.incidents.read_bytes())
        self.assertEqual(self.original_rankings, self.rankings.read_bytes())
        self.assertEqual(self.original_state, self.state.read_bytes())

    def test_delivery_release_guard_never_constructs_provider_or_mutates_intent(self):
        self.assertEqual(0, self.main("collect", "2026-10-08T15:00:00Z")[0])
        ledger_bytes = self.incidents.read_bytes()
        code, _, error, calls = self.main("deliver", "2026-10-08T15:01:00Z", enabled=False)
        self.assertEqual(1, code)
        self.assertIn("ranking_delivery_disabled", error)
        self.assertEqual(0, calls)
        self.assertEqual(ledger_bytes, self.incidents.read_bytes())

    def test_source_error_classes_before_cutoff_leave_sporting_files_unchanged(self):
        for error, category in (("ranking_source_identity_mismatch", "identity"),
                                ("ranking_source_authentication", "http"),
                                ("ranking_source_timeout", "timeout"),
                                ("ranking_source_schema_changed", "schema"),
                                ("ranking_source_dependency", "unavailable")):
            with self.subTest(error=error):
                code, output, errors, calls = self.main("collect", "2026-10-06T12:00:00Z", Source(error=error))
                self.assertEqual(1, code)
                self.assertIn("freshness=SOURCE_ERROR", output)
                self.assertIn("incident=created", output)
                self.assertIn(f"error={error}", errors)
                self.assertEqual(0, calls)
                event = load_incidents(self.incidents).events[-1]
                self.assertEqual(category, event["source_error_category"])
                self.assertEqual("2026-09-28", event["last_valid_date"])
                self.assertEqual(self.original_rankings, self.rankings.read_bytes())
                self.assertEqual(self.original_state, self.state.read_bytes())
        self.assertEqual(5, len(pending_incidents(load_incidents(self.incidents))))

    def test_source_error_dry_run_previews_without_mutation_or_provider(self):
        code, output, errors, calls = self.main("dry-run", "2026-10-06T12:00:00Z", Source(error="ranking_source_timeout"))
        self.assertEqual(1, code)
        self.assertIn("incident=would_create", output)
        self.assertIn("SOURCE_ERROR", output)
        self.assertIn("ranking_source_timeout", errors)
        self.assertEqual(0, calls)
        self.assertFalse(self.incidents.exists())
        self.assertEqual(self.original_rankings, self.rankings.read_bytes())
        self.assertEqual(self.original_state, self.state.read_bytes())

    def test_corrupt_outbox_does_not_block_source_error_persistence_or_delivery(self):
        self.state.write_text("corrupt sporting outbox")
        code, _, errors, calls = self.main("collect", "2026-10-06T12:00:00Z", Source(error="ranking_source_timeout"))
        self.assertEqual(1, code)
        self.assertIn("ranking_source_timeout", errors)
        self.assertEqual(0, calls)
        self.assertEqual(1, len(pending_incidents(load_incidents(self.incidents))))
        code, _, errors, calls = self.main("deliver", "2026-10-08T15:01:00Z", enabled=True)
        self.assertEqual(1, code)
        self.assertIn("invalid_json_storage", errors)
        self.assertEqual(1, calls)
        self.assertEqual(1, len(self.provider.messages))
        self.assertEqual("provider_accepted", load_incidents(self.incidents).events[-1]["kind"])
        self.assertEqual("corrupt sporting outbox", self.state.read_text())
        self.assertEqual(self.original_rankings, self.rankings.read_bytes())

    def test_sporting_provider_failure_does_not_block_incident_delivery(self):
        self.assertEqual(0, self.main("collect", "2026-10-08T12:00:00Z", Source("2026-10-05"))[0])
        self.assertEqual(1, self.main("collect", "2026-10-08T12:01:00Z", Source(error="ranking_source_timeout"))[0])
        original_send = self.provider.send
        def send(*, message, event_id):
            if message.startswith("ATP Ranking"):
                self.provider.messages.append((message, event_id))
                raise DeliveryError("http_503", 1, retryable=True)
            return original_send(message=message, event_id=event_id)
        self.provider.send = send
        code, _, errors, calls = self.main("deliver", "2026-10-08T15:01:00Z", enabled=True)
        self.assertEqual(1, code)
        self.assertIn("http_503", errors)
        self.assertEqual(1, calls)
        self.assertEqual(2, len(self.provider.messages))
        self.assertEqual("provider_accepted", load_incidents(self.incidents).events[-1]["kind"])
        outbox = load_alert_state(self.state, load_rankings(self.rankings)).outbox
        self.assertEqual("http_503", outbox[-1].last_error_code)

    def test_unexpected_source_exception_is_redacted_and_persisted(self):
        class BrokenSource:
            name = "itf"
            def fetch(self):
                raise RuntimeError("https://private?apikey=secret cookie=private-session")
        code, output, errors, calls = self.main("collect", "2026-10-06T12:00:00Z", BrokenSource())
        self.assertEqual(1, code)
        self.assertEqual(0, calls)
        self.assertNotIn("secret", output + errors + self.incidents.read_text())
        self.assertNotIn("private-session", output + errors + self.incidents.read_text())
        event = load_incidents(self.incidents).events[-1]
        self.assertEqual("unavailable", event["source_error_category"])
        self.assertEqual("ranking_source_incomplete", event["source_error_code"])

    def test_domain_identity_and_incomplete_observations_become_source_errors(self):
        class BrokenSource:
            name = "itf"
            def fetch(self):
                return RawRankingObservation(atp_id="OTHER", name="Luka Bojicic Ono", source="itf",
                    ranking_date="2026-10-05", singles=RawDisciplineRanking(status="ranked", rank=1, points=None),
                    doubles=RawDisciplineRanking(status="ranked", rank=1, points=None))
        code, _, errors, _ = self.main("collect", "2026-10-06T12:00:00Z", BrokenSource())
        self.assertEqual(1, code)
        self.assertIn("ranking_source_identity_mismatch", errors)
        self.assertEqual("identity", load_incidents(self.incidents).events[-1]["source_error_category"])
        with patch.object(BrokenSource, "fetch", return_value={"malformed": True}):
            code, _, errors, _ = self.main("collect", "2026-10-06T12:01:00Z", BrokenSource())
        self.assertEqual(1, code)
        self.assertIn("ranking_source_schema_changed", errors)
        self.assertEqual("schema", load_incidents(self.incidents).events[-1]["source_error_category"])


if __name__ == "__main__":
    unittest.main()
