from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ranking_alerts.incidents import (
    IncidentLedger, classify_source_error, deliver_incidents, format_stale, format_incident, load_incidents,
    pending_incidents, plan_recovery, plan_source_error, plan_stale, save_incidents,
)
from scripts.ranking_alerts.providers import DeliveryError, DeliveryReceipt
from scripts.ranking_alerts.storage import StorageError


def stale(ledger=IncidentLedger(), **overrides):
    values = dict(expected_date="2026-10-05", last_valid_date="2026-09-28",
                  source="itf", cutoff_at="2026-10-08T15:00:00Z", now="2026-10-08T15:00:00Z")
    values.update(overrides)
    return plan_stale(ledger, **values)


class Provider:
    name = "callmebot"
    last_attempt_count = 1

    def __init__(self, error=None):
        self.error = error
        self.messages = []

    def send(self, *, message, event_id):
        self.messages.append((message, event_id))
        if self.error:
            raise self.error
        return DeliveryReceipt(provider=self.name, accepted_at="2026-10-08T15:01:00Z", http_status=200)


class IncidentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.json"

    def test_one_intention_per_expected_edition_even_after_recovery(self):
        original = stale()
        self.assertEqual(original, stale(original))
        recovered = plan_recovery(original, ranking_date="2026-10-05", now="2026-10-09T12:00:00Z")
        self.assertEqual(recovered, stale(recovered))
        self.assertEqual((), pending_incidents(recovered))
        self.assertEqual(original.events, recovered.events[:1])

    def test_cutoff_and_corrupt_ledger_fail_closed(self):
        with self.assertRaises(StorageError):
            stale(now="2026-10-08T14:59:59Z")
        with self.assertRaises(StorageError):
            IncidentLedger(({"kind": "created"},))
        self.assertFalse(self.path.exists())

    def test_recovery_cancels_unsent_incident_without_erasing_audit(self):
        ledger = stale()
        save_incidents(self.path, plan_recovery(ledger, ranking_date="2026-10-12", now="2026-10-12T12:00:00Z"))
        provider = Provider()
        self.assertEqual(0, deliver_incidents(provider=provider, path=self.path, now="2026-10-12T12:00:00Z"))
        self.assertEqual([], provider.messages)
        self.assertEqual(2, len(load_incidents(self.path).events))

    def test_provider_acceptance_is_deduplicated_and_recovery_append_only(self):
        ledger = stale()
        save_incidents(self.path, ledger)
        provider = Provider()
        self.assertEqual(1, deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:01:00Z"))
        self.assertEqual(0, deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:02:00Z"))
        accepted = load_incidents(self.path)
        self.assertEqual("provider_accepted", accepted.events[-1]["kind"])
        self.assertEqual(ledger.events, accepted.events[:1])
        self.assertIn("2026-09-28", provider.messages[0][0])
        self.assertNotIn("#", format_stale(ledger.events[0]))
        self.assertEqual("ranking_stale:2026-10-05", provider.messages[0][1])

    def test_retryable_failure_and_permanent_failure_survive_reload(self):
        for retryable in (True, False):
            with self.subTest(retryable=retryable):
                path = self.path.with_name(f"ledger-{retryable}.json")
                save_incidents(path, stale())
                provider = Provider(DeliveryError("http_500" if retryable else "http_401", 1, retryable=retryable))
                with self.assertRaises(DeliveryError):
                    deliver_incidents(provider=provider, path=path, now="2026-10-08T15:01:00Z")
                failed = load_incidents(path)
                self.assertEqual("provider_failed", failed.events[-1]["kind"])
                self.assertEqual(1 if retryable else 0, len(pending_incidents(failed)))
                self.assertEqual(stale().events, failed.events[:1])

    def source_error(self, ledger=IncidentLedger(), code="ranking_source_timeout", **overrides):
        details = dict(expected_date="2026-10-05", last_valid_date="2026-09-28", source="itf",
                       cutoff_at="2026-10-08T15:00:00Z", now="2026-10-06T12:00:00Z", error_code=code)
        details.update(overrides)
        return plan_source_error(ledger, **details)

    def test_source_classes_are_deduplicated_per_class_and_edition(self):
        ledger = stale()
        for code, category in (("ranking_source_identity_mismatch", "identity"),
                               ("ranking_source_blocked", "http"),
                               ("ranking_source_timeout", "timeout"),
                               ("ranking_source_schema_changed", "schema"),
                               ("ranking_source_navigation", "unavailable")):
            ledger = self.source_error(ledger, code)
            event = ledger.events[-1]
            self.assertEqual(f"ranking_source_error:{category}:2026-10-05", event["incident_id"])
            self.assertEqual(category, event["source_error_category"])
            self.assertEqual(ledger, self.source_error(ledger, code))
        self.assertEqual(6, len(pending_incidents(ledger)))
        recovered = plan_recovery(ledger, ranking_date="2026-10-05", now="2026-10-09T12:00:00Z")
        self.assertEqual(12, len(recovered.events))
        self.assertEqual((), pending_incidents(recovered))
        self.assertEqual(recovered, plan_recovery(recovered, ranking_date="2026-10-05", now="2026-10-09T13:00:00Z"))
        self.assertEqual(recovered, self.source_error(recovered))

    def test_http_status_classifies_generic_itf_failure_without_retaining_response(self):
        telemetry = {"singles": {"http_status": 503, "body": "secret-cookie"}, "final_url": "private"}
        ledger = self.source_error(code="ranking_source_incomplete", telemetry=telemetry)
        self.assertEqual("http", ledger.events[0]["source_error_category"])
        self.assertEqual("timeout", classify_source_error("ranking_source_timeout", telemetry=telemetry))
        save_incidents(self.path, ledger)
        self.assertNotIn("secret", self.path.read_text())
        self.assertNotIn("private", format_incident(ledger.events[0]))
        self.assertIn("SOURCE_ERROR", format_incident(ledger.events[0]))
        with self.assertRaises(StorageError):
            self.source_error(code="https://private?apikey=secret")

    def test_save_rejects_truncation_and_mutation_preserving_audit_bytes(self):
        original = stale()
        save_incidents(self.path, original)
        before = self.path.read_bytes()
        for replacement in (IncidentLedger(), stale(source="atptour")):
            with self.subTest(replacement=replacement), self.assertRaises(StorageError):
                save_incidents(self.path, replacement)
            self.assertEqual(before, self.path.read_bytes())
        save_incidents(self.path, plan_recovery(original, ranking_date="2026-10-05", now="2026-10-09T12:00:00Z"))
        self.assertEqual(original.events, load_incidents(self.path).events[:1])

    def test_legacy_v1_accepted_failed_and_recovered_ledgers_remain_readable(self):
        initial = stale().events[0]
        failed = {**initial, "kind": "provider_failed", "at": "2026-10-08T15:01:00Z",
                  "attempts": 4, "error_code": "http_500"}
        accepted = {**failed, "kind": "provider_accepted", "at": "2026-10-08T15:02:00Z",
                    "attempts": 5, "retryable": False, "error_code": None}
        legacy = IncidentLedger((initial, failed, accepted))
        save_incidents(self.path, legacy)
        self.assertEqual(legacy, load_incidents(self.path))
        recovered = plan_recovery(legacy, ranking_date="2026-10-05", now="2026-10-09T12:00:00Z")
        save_incidents(self.path, recovered)
        self.assertEqual(recovered, load_incidents(self.path))

    def test_checkpoint_observes_claim_before_send_and_result_before_return(self):
        save_incidents(self.path, self.source_error())
        provider = Provider()
        checkpoints = []
        def checkpoint():
            event = load_incidents(self.path).events[-1]
            checkpoints.append((event["kind"], len(provider.messages), event["attempts"]))
            self.assertFalse(event["retryable"])
        self.assertEqual(1, deliver_incidents(provider=provider, path=self.path,
                                             now="2026-10-08T15:01:00Z", checkpoint=checkpoint))
        self.assertEqual([("provider_in_flight", 0, 1), ("provider_accepted", 1, 1)], checkpoints)

    def test_failed_claim_checkpoint_prevents_send_and_automatic_replay(self):
        save_incidents(self.path, stale())
        provider = Provider()
        def checkpoint():
            raise RuntimeError("private remote credentials")
        with self.assertRaisesRegex(StorageError, "incident_checkpoint_failed"):
            deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:01:00Z", checkpoint=checkpoint)
        self.assertEqual([], provider.messages)
        self.assertEqual("provider_in_flight", load_incidents(self.path).events[-1]["kind"])
        self.assertEqual(0, deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:02:00Z"))
        self.assertNotIn("private", self.path.read_text())

    def test_process_interrupted_after_send_does_not_replay_on_reload(self):
        save_incidents(self.path, stale())
        provider = Provider(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:01:00Z")
        self.assertEqual(1, len(provider.messages))
        self.assertEqual("provider_in_flight", load_incidents(self.path).events[-1]["kind"])
        self.assertEqual(0, deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:02:00Z"))

    def test_acceptance_persistence_failure_retains_claim_without_replay(self):
        save_incidents(self.path, stale())
        provider = Provider()
        from scripts.ranking_alerts import incidents
        original = incidents.save_incidents
        def save(path, ledger):
            if ledger.events[-1]["kind"] == "provider_accepted":
                raise StorageError("storage_write_failed")
            original(path, ledger)
        with patch.object(incidents, "save_incidents", side_effect=save), self.assertRaises(StorageError):
            deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:01:00Z")
        self.assertEqual("provider_in_flight", load_incidents(self.path).events[-1]["kind"])
        self.assertEqual(0, deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:02:00Z"))
        self.assertEqual(1, len(provider.messages))

    def test_uncertain_provider_failures_are_audited_without_automatic_retry(self):
        for code in ("transport_timeout", "transport_error", "provider_response_ambiguous", "http_408"):
            path = self.path.with_name(f"{code}.json")
            save_incidents(path, stale())
            provider = Provider(DeliveryError(code, 2, retryable=True))
            with self.subTest(code=code), self.assertRaises(DeliveryError):
                deliver_incidents(provider=provider, path=path, now="2026-10-08T15:01:00Z")
            failed = load_incidents(path).events[-1]
            self.assertEqual("provider_failed", failed["kind"])
            self.assertEqual(2, failed["attempts"])
            self.assertFalse(failed["retryable"])
            self.assertEqual(0, deliver_incidents(provider=provider, path=path, now="2026-10-08T15:02:00Z"))

    def test_uncertain_legacy_timeout_is_not_automatically_replayed(self):
        initial = stale().events[0]
        failed = {**initial, "kind": "provider_failed", "at": "2026-10-08T15:01:00Z",
                  "attempts": 4, "error_code": "transport_timeout"}
        save_incidents(self.path, IncidentLedger((initial, failed)))
        provider = Provider()
        self.assertEqual(0, deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:02:00Z"))
        self.assertEqual([], provider.messages)

    def test_provider_failure_does_not_block_independent_incident(self):
        save_incidents(self.path, self.source_error(stale()))
        provider = Provider()
        original_send = provider.send
        def send(*, message, event_id):
            if event_id.startswith("ranking_stale:"):
                raise DeliveryError("http_500", 1, retryable=True)
            return original_send(message=message, event_id=event_id)
        provider.send = send
        with self.assertRaises(DeliveryError):
            deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:01:00Z")
        latest = load_incidents(self.path).latest()
        self.assertEqual("provider_failed", latest["ranking_stale:2026-10-05"]["kind"])
        self.assertEqual("provider_accepted", latest["ranking_source_error:timeout:2026-10-05"]["kind"])

    def test_unexpected_provider_failure_is_redacted_and_audited(self):
        save_incidents(self.path, stale())
        provider = Provider(RuntimeError("https://private?apikey=secret phone=+12345678"))
        with self.assertRaisesRegex(DeliveryError, "provider_error"):
            deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:01:00Z")
        self.assertEqual("provider_error", load_incidents(self.path).events[-1]["error_code"])
        self.assertNotIn("secret", self.path.read_text())

    def test_retry_claim_uses_new_nonce_and_keeps_first_attempt_audit(self):
        save_incidents(self.path, stale())
        provider = Provider(DeliveryError("http_503", 1, retryable=True))
        with self.assertRaises(DeliveryError):
            deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:01:00Z")
        first = load_incidents(self.path)
        provider.error = None
        self.assertEqual(1, deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:01:00Z"))
        events = load_incidents(self.path).events
        self.assertEqual(first.events, events[:3])
        self.assertNotEqual(events[1]["attempt_id"], events[3]["attempt_id"])
        self.assertEqual(events[1]["attempt_id"], events[2]["attempt_id"])
        self.assertEqual(events[3]["attempt_id"], events[4]["attempt_id"])
        self.assertEqual(2, events[-1]["attempts"])

    def test_result_checkpoint_failure_prevents_next_incident_send(self):
        save_incidents(self.path, self.source_error(stale()))
        provider = Provider()
        def checkpoint():
            if load_incidents(self.path).events[-1]["kind"] == "provider_accepted":
                raise RuntimeError("private Git URL")
        with self.assertRaisesRegex(StorageError, "incident_checkpoint_failed"):
            deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:01:00Z", checkpoint=checkpoint)
        self.assertEqual(1, len(provider.messages))
        latest = load_incidents(self.path).latest()
        self.assertEqual("provider_accepted", latest["ranking_stale:2026-10-05"]["kind"])
        self.assertEqual("created", latest["ranking_source_error:timeout:2026-10-05"]["kind"])


if __name__ == "__main__":
    unittest.main()
