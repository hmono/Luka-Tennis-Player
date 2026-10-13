from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
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

    def main(self, command, instant, source=Source(), enabled=False, incidents_only=False):
        args = [command, "--provider" if command == "deliver" else "--source", "callmebot" if command == "deliver" else "itf",
                "--rankings-path", str(self.rankings), "--state-path", str(self.state), "--incidents-path", str(self.incidents)]
        if incidents_only:
            args.append("--incidents-only")
        output, errors = StringIO(), StringIO()
        with patch.object(update_rankings, "_selected_source", return_value=source), \
             patch.object(update_rankings.CallMeBotProvider, "from_env", return_value=self.provider) as factory, \
             patch.dict("os.environ", {"ATP_RANKING_DELIVERY_ENABLED": "true" if enabled else "false"}), \
             redirect_stdout(output), redirect_stderr(errors):
            result = update_rankings.main(args, clock=lambda: datetime.fromisoformat(instant.replace("Z", "+00:00")), checkpoint=lambda: None)
        return result, output.getvalue(), errors.getvalue(), factory.call_count

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
