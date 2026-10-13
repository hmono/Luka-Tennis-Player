"""Local durable pipeline faults; no network, credentials or provider calls."""
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.ranking_alerts.autonomous_scheduler import WatchdogStore, watchdog_cycle
from scripts.ranking_alerts.ops_receiver import OpsInbox


class DisabledWorkflow:
    def inspect(self):
        return 'disabled_manually', []

    def dispatch(self):
        raise AssertionError('disabled workflow must never dispatch')


class Ops26PipelineTests(unittest.TestCase):
    def test_lost_ack_at_both_hops_replays_without_losing_or_duplicating_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inbox = OpsInbox(root / 'inbox')
            store = WatchdogStore(root / 'watchdog')
            now = datetime(2026, 10, 13, 14, tzinfo=timezone.utc)

            def accept_then_lose_ack(event_id, message):
                inbox.accept(event_id, message)
                raise TimeoutError('synthetic timeout after durable commit')

            first = watchdog_cycle(now=now, client=DisabledWorkflow(), store=store,
                                   sender=accept_then_lose_ack, released=True,
                                   recovery_enabled=True)
            self.assertEqual(0, first['alerts_accepted'])
            self.assertEqual(1, inbox.status()['persisted_events'])
            store.close()

            # Restart both processes, retaining their independently persisted state.
            inbox = OpsInbox(root / 'inbox')
            store = WatchdogStore(root / 'watchdog')
            try:
                def accept_replay(event_id, message):
                    self.assertFalse(inbox.accept(event_id, message))
                    return True

                second = watchdog_cycle(now=now + timedelta(minutes=10),
                                        client=DisabledWorkflow(), store=store,
                                        sender=accept_replay, released=True,
                                        recovery_enabled=True)
                self.assertEqual(1, second['alerts_accepted'])
                self.assertEqual(0, second['recoveries'])
                self.assertEqual(1, store.connection.execute(
                    "SELECT count(*) FROM alerts WHERE status='accepted'").fetchone()[0])
            finally:
                store.close()

            sink = root / 'synthetic-sink.sqlite3'
            with sqlite3.connect(sink) as database:
                database.execute('CREATE TABLE receipts(id TEXT PRIMARY KEY, message TEXT)')

            def durable_sink(event_id, message, lose_ack=False):
                with sqlite3.connect(sink) as database:
                    database.execute('INSERT OR IGNORE INTO receipts VALUES (?, ?)',
                                     (event_id, message))
                    self.assertEqual(message, database.execute(
                        'SELECT message FROM receipts WHERE id=?', (event_id,)).fetchone()[0])
                if lose_ack:
                    raise TimeoutError('synthetic timeout after sink commit')
                return True

            self.assertEqual(0, inbox.forward(lambda e, m: durable_sink(e, m, True)))
            self.assertEqual(1, inbox.status()['pending_forwarding'])
            inbox = OpsInbox(root / 'inbox')
            self.assertEqual(1, inbox.forward(durable_sink))
            self.assertEqual(0, inbox.forward(durable_sink))
            self.assertEqual(0, inbox.status()['pending_forwarding'])
            with sqlite3.connect(sink) as database:
                self.assertEqual(1, database.execute('SELECT count(*) FROM receipts').fetchone()[0])
                self.assertEqual('ok', database.execute('PRAGMA integrity_check').fetchone()[0])
