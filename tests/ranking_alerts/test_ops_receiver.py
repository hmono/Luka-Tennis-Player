import tempfile
import unittest
from pathlib import Path
from scripts.ranking_alerts.ops_receiver import OpsInbox


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
