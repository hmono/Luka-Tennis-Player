from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.ranking_alerts.incidents import (
    IncidentLedger, deliver_incidents, format_stale, load_incidents,
    pending_incidents, plan_recovery, plan_stale, save_incidents,
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
                save_incidents(self.path, stale())
                provider = Provider(DeliveryError("http_500" if retryable else "http_401", 1, retryable=retryable))
                with self.assertRaises(DeliveryError):
                    deliver_incidents(provider=provider, path=self.path, now="2026-10-08T15:01:00Z")
                failed = load_incidents(self.path)
                self.assertEqual("provider_failed", failed.events[-1]["kind"])
                self.assertEqual(1 if retryable else 0, len(pending_incidents(failed)))
                self.assertEqual(stale().events, failed.events[:1])


if __name__ == "__main__":
    unittest.main()
