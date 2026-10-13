from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS)) if str(SCRIPTS) not in sys.path else None
from ranking_alerts.autonomous_delivery import (
    DeliveryLedger, deliver_autonomously, load_delivery, plan_digest,
    plan_operational, plan_weekly_status, save_delivery,
)
from ranking_alerts.domain import (
    DisciplineRanking, OutboxItem, RankingAlertState, RankingObservation, RankingsData,
    build_snapshot, event_id,
)
from ranking_alerts.providers import DeliveryError, DeliveryReceipt
from ranking_alerts.storage import StorageError

SNAPSHOT = "sha256:" + "a" * 64


class MockProvider:
    name = "callmebot"

    def __init__(self, error=None, before_send=None):
        self.error, self.before_send = error, before_send
        self.calls = []

    def send(self, **kwargs):
        if self.before_send:
            self.before_send()
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return DeliveryReceipt(provider=self.name, accepted_at="2026-10-13T12:00:00Z", http_status=200)


class AutonomousDeliveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "ranking_delivery.json"
        self.clock = "2026-10-13T12:00:00Z"
        self.checkpoints = []

    def plan(self, **kwargs):
        return plan_digest(load_delivery(self.path), snapshot_id=SNAPSHOT,
                           ranking_date=kwargs.pop("ranking_date", "2026-10-12"),
                           message="ATP edition with same ranks, deltas and CH", now=self.clock, **kwargs)

    def run_delivery(self, provider, **kwargs):
        return deliver_autonomously(path=self.path, provider=provider,
                                    checkpoint=lambda: self.checkpoints.append(self.path.read_text()),
                                    now=lambda: self.clock, **kwargs)

    def test_remote_reservation_before_send_acceptance_not_device_delivery(self):
        save_delivery(self.path, self.plan())
        def before_send():
            latest = load_delivery(self.path).latest()["edition:2026-10-12"]
            self.assertEqual(latest["state"], "reserved")
            self.assertEqual(len(latest["attempt_id"]), 32)
            self.assertEqual(len(self.checkpoints), 2)
        provider = MockProvider(before_send=before_send)
        report = self.run_delivery(provider)
        self.assertEqual(report.accepted, 1)
        item = load_delivery(self.path).latest()["edition:2026-10-12"]
        self.assertEqual(item["state"], "provider_accepted")
        self.assertFalse(item["delivered_to_device"])
        self.run_delivery(provider)
        self.assertEqual(len(provider.calls), 1)

    def test_checkpoint_failure_never_sends_and_recovery_terminates(self):
        save_delivery(self.path, self.plan())
        provider = MockProvider()
        def failed_checkpoint():
            if any(i["state"] == "reserved" for i in load_delivery(self.path).latest().values()):
                raise StorageError("ranking_checkpoint_failed")
        with self.assertRaises(StorageError):
            deliver_autonomously(path=self.path, provider=provider, checkpoint=failed_checkpoint, now=lambda: self.clock)
        self.assertEqual(provider.calls, [])
        alerts = []
        report = self.run_delivery(provider, ops_alert=lambda event, message: alerts.append((event, message)) or True)
        self.assertEqual(report.unknown, 1)
        self.assertEqual(provider.calls, [])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(load_delivery(self.path).latest()["edition:2026-10-12"]["risk"], "possible_loss")

    def test_ambiguous_timeout_and_unknown_adapter_do_not_replay_and_alert_independently(self):
        for error in (DeliveryError("transport_timeout", 1), DeliveryError("provider_response_ambiguous", 1), RuntimeError("apikey=secret")):
            with self.subTest(error=type(error).__name__):
                self.path.unlink(missing_ok=True)
                save_delivery(self.path, self.plan())
                provider, alerts = MockProvider(error), []
                self.run_delivery(provider, ops_alert=lambda event, message: alerts.append(message) or True)
                self.run_delivery(provider, ops_alert=lambda event, message: alerts.append(message) or True)
                self.assertEqual(len(provider.calls), 1)
                self.assertEqual(len(alerts), 1)
                text = self.path.read_text()
                self.assertNotIn("apikey", text)
                self.assertIn("delivery_unknown", text)
                self.assertIn("possible_loss", text)

    def test_durable_429_backoff_exhausts_without_blocking_future_editions(self):
        save_delivery(self.path, self.plan())
        provider = MockProvider(DeliveryError("http_429", 1, retryable=True))
        report = self.run_delivery(provider, max_attempts=3)
        self.assertEqual(report.retrying, 1)
        self.run_delivery(provider, max_attempts=3)
        self.assertEqual(len(provider.calls), 1)
        self.clock = "2026-10-13T12:01:00Z"
        self.run_delivery(provider, max_attempts=3)
        self.assertEqual(len(provider.calls), 2)
        self.clock = "2026-10-13T12:03:00Z"
        report = self.run_delivery(provider, max_attempts=3)
        self.assertEqual(report.rejected, 1)
        save_delivery(self.path, self.plan(ranking_date="2026-10-19"))
        provider.error = None
        self.run_delivery(provider)
        self.assertEqual(len(provider.calls), 4)

    def test_eight_weeks_delays_and_equal_rank_new_edition_once(self):
        provider = MockProvider()
        start = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        for week in range(8):
            self.clock = (start + timedelta(weeks=week)).strftime("%Y-%m-%dT%H:%M:%SZ")
            period = self.clock[:10]
            ledger = load_delivery(self.path)
            if week in {3, 6}:
                ledger = self.plan(ranking_date=period)
            ledger = plan_weekly_status(ledger, period=period, last_verified_date="2026-10-05", checked_at=self.clock, now=self.clock)
            save_delivery(self.path, ledger)
            self.run_delivery(provider)
            # Repeated checks during same week do not duplicate even with old data.
            ledger = plan_weekly_status(load_delivery(self.path), period=period, last_verified_date="2026-10-05", checked_at=self.clock, now=self.clock)
            save_delivery(self.path, ledger)
            self.run_delivery(provider)
        self.assertEqual(len(provider.calls), 10)
        latest = load_delivery(self.path).latest()
        self.assertEqual(sum(i["event_type"] == "edition_digest" for i in latest.values()), 2)
        self.assertEqual(sum(i["event_type"] == "weekly_status" for i in latest.values()), 8)
        self.assertIn("Última classificação verificada: 2026-10-05", provider.calls[0]["message"])

    def test_legacy_accepted_and_ambiguous_are_preserved_without_replay(self):
        for status, code, retryable in (("sent", None, False), ("pending", "transport_timeout", True), ("pending", "provider_outcome_unknown", False)):
            with self.subTest(status=status, code=code):
                self.path.unlink(missing_ok=True)
                item = OutboxItem(id=event_id(SNAPSHOT, "weekly_digest"), snapshot_id=SNAPSHOT, event_type="weekly_digest",
                                  status=status, attempts=1, created_at=self.clock,
                                  sent_at=self.clock if status == "sent" else None, last_error_code=code, retryable=retryable)
                legacy = RankingAlertState(outbox=(item,))
                save_delivery(self.path, self.plan(legacy_state=legacy))
                provider = MockProvider()
                self.run_delivery(provider)
                self.assertEqual(provider.calls, [])
                self.assertEqual(legacy.outbox[0], item)

    def test_old_pending_backlog_suppressed_without_erasing_intentions(self):
        ledger = self.plan(ranking_date="2026-09-28")
        ledger = plan_digest(ledger, snapshot_id=SNAPSHOT, ranking_date="2026-10-12", message="new", now=self.clock)
        ledger = plan_weekly_status(ledger, period="2026-10-05", last_verified_date="2026-09-28", checked_at=self.clock, now=self.clock)
        save_delivery(self.path, ledger)
        provider = MockProvider()
        self.run_delivery(provider)
        latest = load_delivery(self.path).latest()
        self.assertEqual(latest["edition:2026-09-28"]["state"], "suppressed")
        self.assertEqual(latest["status:2026-10-05"]["state"], "suppressed")
        self.assertEqual(len(provider.calls), 1)
        self.assertGreater(len(load_delivery(self.path).events), len(latest))

    def test_operational_alert_runs_without_sporting_provider_and_retries_sink(self):
        ledger = plan_operational(DeliveryLedger(), event_id="source_error:2026-10-13", message="Source unavailable", now=self.clock)
        save_delivery(self.path, ledger)
        report = self.run_delivery(None, ops_alert=lambda event, message: False)
        self.assertEqual(report.ops_pending, 1)
        self.clock = "2026-10-13T12:01:00Z"
        report = self.run_delivery(None, ops_alert=lambda event, message: True)
        self.assertEqual(report.ops_pending, 0)

    def test_ops_retries_past_sporting_cap_and_recovers_crashed_reservation(self):
        ledger = plan_operational(DeliveryLedger(), event_id="source_error", message="Source unavailable", now=self.clock)
        save_delivery(self.path, ledger)
        for attempt in range(6):
            self.clock = f"2026-10-13T{12 + attempt:02d}:00:00Z"
            report = self.run_delivery(None, ops_alert=lambda event, message: False, max_attempts=2)
            self.assertEqual(report.ops_pending, 1)
        latest = next(iter(load_delivery(self.path).latest().values()))
        self.assertEqual(latest["attempts"], 6)
        self.clock = "2026-10-13T18:00:00Z"
        def interrupt(event, message):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_delivery(None, ops_alert=interrupt)
        self.clock = "2026-10-13T18:01:00Z"
        self.run_delivery(None, ops_alert=lambda event, message: True)
        self.clock = "2026-10-13T18:02:00Z"
        report = self.run_delivery(None, ops_alert=lambda event, message: True)
        self.assertEqual(report.ops_pending, 0)
        self.assertFalse(any(i["state"] == "delivery_unknown" for i in load_delivery(self.path).latest().values()))

    def test_legacy_revision_receipt_prevents_new_revision_duplicate(self):
        old = build_snapshot(RankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", ranking_date="2026-10-12",
                             singles=DisciplineRanking(rank=2250, points=None), doubles=DisciplineRanking(rank=1417, points=None)), captured_at=self.clock)
        item = OutboxItem(id=event_id(old.id, "weekly_digest"), snapshot_id=old.id,
                         event_type="weekly_digest", status="sent", attempts=1,
                         created_at=self.clock, sent_at=self.clock)
        legacy = RankingAlertState(outbox=(item,))
        save_delivery(self.path, self.plan(legacy_state=legacy, legacy_rankings=RankingsData(snapshots=(old,))))
        provider = MockProvider()
        self.run_delivery(provider)
        self.assertEqual(provider.calls, [])

    def test_rejected_revision_replaced_before_retry_without_old_facts(self):
        save_delivery(self.path, self.plan())
        provider = MockProvider(DeliveryError("http_429", 1, retryable=True))
        self.run_delivery(provider)
        self.clock = "2026-10-13T12:01:00Z"
        ledger = plan_digest(load_delivery(self.path), snapshot_id="sha256:" + "b" * 64,
                             ranking_date="2026-10-12", message="corrected edition B", now=self.clock)
        save_delivery(self.path, ledger)
        provider.error = None
        self.run_delivery(provider)
        self.assertEqual(provider.calls[-1]["message"], "corrected edition B")
        self.assertEqual(len(provider.calls), 2)
        ledger = self.plan()
        save_delivery(self.path, ledger)
        self.run_delivery(provider)
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(load_delivery(self.path).latest()["edition:2026-10-12"]["state"], "suppressed")

    def test_unattempted_revision_a_b_a_uses_latest_intention_once(self):
        ledger = self.plan()
        ledger = plan_digest(ledger, snapshot_id="sha256:" + "b" * 64, ranking_date="2026-10-12", message="B", now=self.clock)
        ledger = plan_digest(ledger, snapshot_id=SNAPSHOT, ranking_date="2026-10-12", message="A restored", now=self.clock)
        save_delivery(self.path, ledger)
        provider = MockProvider()
        self.run_delivery(provider)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]["message"], "A restored")
        states = [i["state"] for i in load_delivery(self.path).latest().values()]
        self.assertEqual(states.count("suppressed"), 2)
        self.assertEqual(states.count("provider_accepted"), 1)

    def test_weekly_backlog_boundary_is_monday_09_sao_paulo(self):
        self.clock = "2026-10-12T11:59:00Z"  # Monday 08:59 BRT.
        ledger = plan_weekly_status(DeliveryLedger(), period="2026-10-05",
                                   last_verified_date="2026-10-05", checked_at=self.clock, now=self.clock)
        save_delivery(self.path, ledger)
        self.run_delivery(None)
        self.assertEqual(load_delivery(self.path).latest()["status:2026-10-05"]["state"], "planned")
        self.clock = "2026-10-12T12:00:00Z"  # Monday 09:00 BRT.
        self.run_delivery(None)
        self.assertEqual(load_delivery(self.path).latest()["status:2026-10-05"]["state"], "suppressed")

    def test_append_only_integrity_and_false_device_claim_fail_closed(self):
        ledger = self.plan()
        save_delivery(self.path, ledger)
        with self.assertRaises(StorageError):
            save_delivery(self.path, DeliveryLedger())
        with self.assertRaises(StorageError):
            DeliveryLedger(({**ledger.events[0], "delivered_to_device": True},))
        with self.assertRaises(StorageError):
            DeliveryLedger(({**ledger.events[0], "at": "garbage"},))


if __name__ == "__main__":
    unittest.main()
