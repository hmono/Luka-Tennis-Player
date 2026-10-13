import tempfile
import os
import sqlite3
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.ranking_alerts.ops_receiver import OpsInbox, forward_loop, forward_sender


class OpsInboxTests(unittest.TestCase):
    def test_persistent_dedup_and_conflicting_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            inbox = OpsInbox(Path(directory))
            self.assertTrue(inbox.accept('event', 'scheduler unavailable'))
            restarted = OpsInbox(Path(directory))
            self.assertFalse(restarted.accept('event', 'scheduler unavailable'))
            with self.assertRaises(ValueError):
                restarted.accept('event', 'different')
            self.assertEqual(1, restarted.status()['persisted_events'])

    def test_forwarding_outage_retries_from_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            inbox = OpsInbox(Path(directory))
            inbox.accept('event', 'source unknown')
            self.assertEqual(0, inbox.forward(lambda *_: False))
            restarted = OpsInbox(Path(directory))
            accepted = []
            self.assertEqual(1, restarted.forward(lambda event, message: accepted.append(event) or True))
            self.assertEqual(0, restarted.forward(lambda event, message: accepted.append(event) or True))
            self.assertEqual(['event'], accepted)
            self.assertEqual(0, restarted.status()['pending_forwarding'])

    def test_real_database_lock_recovers_forwarding_without_service_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            inbox = OpsInbox(Path(directory))
            inbox.accept('event', 'source unknown')
            locked = inbox.connect()
            locked.execute('BEGIN EXCLUSIVE')
            stop, delivered = threading.Event(), threading.Event()
            def quick_connect():
                return sqlite3.connect(inbox.path, timeout=0.02)
            def sender(*_):
                delivered.set()
                return True
            with patch.object(inbox, 'connect', side_effect=quick_connect):
                thread = threading.Thread(target=forward_loop, args=(inbox, sender),
                                          kwargs={'stop': stop, 'interval': 0.01})
                thread.start()
                try:
                    deadline = time.monotonic() + 2
                    while inbox.forwarding_failures == 0 and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertGreater(inbox.forwarding_failures, 0)
                    self.assertTrue(thread.is_alive())
                    self.assertFalse(delivered.is_set())
                    locked.rollback()
                    locked.close()
                    self.assertTrue(delivered.wait(2))
                finally:
                    stop.set()
                    thread.join(2)
                    try:
                        locked.close()
                    except sqlite3.Error:
                        pass
            self.assertFalse(thread.is_alive())
            self.assertEqual(0, inbox.status()['pending_forwarding'])

    def test_forwarding_requires_explicit_durable_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            inbox = OpsInbox(Path(directory))
            inbox.accept('event', 'source unknown')
            with patch.dict(os.environ, {'ATP_OPS_FORWARD_URL': 'https://ops.example.test/events'}, clear=True), \
                 patch('scripts.ranking_alerts.ops_receiver._request') as request:
                for response in ({'accepted': False}, {}, {'accepted': 1}):
                    request.return_value = response
                    self.assertEqual(0, inbox.forward(forward_sender))
                    self.assertEqual(1, inbox.status()['pending_forwarding'])
                request.return_value = {'accepted': True}
                self.assertEqual(1, inbox.forward(forward_sender))
                self.assertEqual(0, inbox.status()['pending_forwarding'])
