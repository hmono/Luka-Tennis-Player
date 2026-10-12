from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS)) if str(SCRIPTS) not in sys.path else None
import update_rankings
from ranking_alerts.domain import (
    DisciplineRanking, RankingAlertState, RankingObservation, RankingsData,
    state_from_dict, state_to_dict,
)
from ranking_alerts.providers import DeliveryError, DeliveryReceipt
from ranking_alerts.storage import load_alert_state, save_alert_state, save_rankings


class MockProvider:
    name = "callmebot"
    last_attempt_count = 1

    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def send(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return DeliveryReceipt(provider=self.name, accepted_at="2026-10-06T12:01:00Z", http_status=200)


class DeliveryStateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.rankings_path, self.state_path = Path(temp.name) / "rankings.json", Path(temp.name) / "state.json"
        observation = RankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
            ranking_date="2026-10-05", singles=DisciplineRanking(rank=2250, points=None),
            doubles=DisciplineRanking(rank=1417, points=None))
        outcome = update_rankings.plan_collection(RankingsData(), RankingAlertState(), observation,
                                                  captured_at="2026-10-06T12:00:00Z")
        save_rankings(self.rankings_path, outcome.rankings)
        save_alert_state(self.state_path, outcome.state, outcome.rankings)

    def deliver(self, provider):
        return update_rankings.deliver(provider=provider, rankings_path=self.rankings_path, state_path=self.state_path)

    def test_permanent_and_ambiguous_failures_remain_auditable_without_automatic_retry(self):
        for code in ("http_401", "provider_response_ambiguous"):
            with self.subTest(code=code):
                self.setUp()
                provider = MockProvider(DeliveryError(code, 1, retryable=False))
                with self.assertRaises(DeliveryError):
                    self.deliver(provider)
                state = load_alert_state(self.state_path, update_rankings.load_rankings(self.rankings_path))
                self.assertEqual("pending", state.outbox[0].status)
                self.assertFalse(state.outbox[0].retryable)
                self.assertEqual(0, self.deliver(provider))
                self.assertEqual(1, provider.calls)
                self.assertFalse(update_rankings.has_pending_outbox(rankings_path=self.rankings_path, state_path=self.state_path))

    def test_receipt_is_provider_acceptance_and_rerun_is_noop(self):
        provider = MockProvider()
        self.assertEqual(1, self.deliver(provider))
        state = load_alert_state(self.state_path, update_rankings.load_rankings(self.rankings_path))
        self.assertEqual("provider_accepted", state.outbox[0].delivery_status)
        self.assertEqual("sent", state.outbox[0].status)
        self.assertEqual(0, self.deliver(provider))
        self.assertEqual(1, provider.calls)

    def test_legacy_receipt_roundtrip_does_not_invent_device_delivery(self):
        import json
        old = json.loads(self.state_path.read_text())
        self.assertNotIn("delivery_status", old["outbox"][0])
        self.assertEqual(old, state_to_dict(state_from_dict(old)))


if __name__ == "__main__":
    unittest.main()
