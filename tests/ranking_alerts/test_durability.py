from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ranking_alerts import collection_transaction as tx
from ranking_alerts.domain import DisciplineRanking, RankingObservation, RankingsData, RankingAlertState
from ranking_alerts.durability import GitCheckpoint, state_lock
from ranking_alerts.storage import StorageError, load_alert_state, load_rankings, write_json_atomic
import update_rankings


class CollectionTransactionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.rankings, self.state = self.root / "rankings.json", self.root / "state.json"
        observation = RankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
            ranking_date="2026-10-05", singles=DisciplineRanking(rank=2250, points=None),
            doubles=DisciplineRanking(rank=1417, points=None))
        self.outcome = update_rankings.plan_collection(RankingsData(), RankingAlertState(), observation,
                                                     captured_at="2026-10-06T12:00:00Z")

    def test_second_write_failure_replays_intention_without_new_observation(self):
        with patch.object(tx, "save_alert_state", side_effect=StorageError("storage_write_failed")):
            with self.assertRaises(StorageError):
                tx.save_collection(self.rankings, self.state, rankings=self.outcome.rankings, state=self.outcome.state)
        self.assertTrue(self.rankings.exists())
        self.assertFalse(self.state.exists())
        self.assertTrue(tx.journal_path(self.state).exists())
        tx.recover_collection(self.rankings, self.state)
        self.assertEqual(self.outcome.rankings, load_rankings(self.rankings))
        self.assertEqual(self.outcome.state, load_alert_state(self.state, self.outcome.rankings))
        self.assertFalse(tx.journal_path(self.state).exists())
        original = self.state.read_bytes()
        tx.recover_collection(self.rankings, self.state)
        self.assertEqual(original, self.state.read_bytes())

    def test_replay_does_not_overwrite_concurrent_receipt_or_other_state(self):
        with patch.object(tx, "save_alert_state", side_effect=StorageError("storage_write_failed")):
            with self.assertRaises(StorageError):
                tx.save_collection(self.rankings, self.state, rankings=self.outcome.rankings, state=self.outcome.state)
        self.state.write_text('{"schema_version":1,"outbox":[]}')
        before = self.state.read_bytes()
        with self.assertRaisesRegex(StorageError, "collection_transaction_conflict"):
            tx.recover_collection(self.rankings, self.state)
        self.assertEqual(before, self.state.read_bytes())

    def test_no_journal_never_invents_backfill_notification(self):
        tx.save_rankings(self.rankings, self.outcome.rankings)
        tx.recover_collection(self.rankings, self.state)
        self.assertFalse(self.state.exists())

    def test_recovery_is_replayed_with_snapshot_and_outbox_after_third_write_failure(self):
        from ranking_alerts.incidents import IncidentLedger, plan_stale, plan_recovery, save_incidents, load_incidents
        incidents_path = self.root / "incidents.json"
        original = plan_stale(IncidentLedger(), expected_date="2026-10-05", last_valid_date="2026-09-28",
                              source="itf", cutoff_at="2026-10-08T15:00:00Z", now="2026-10-08T15:00:00Z")
        save_incidents(incidents_path, original)
        recovered = plan_recovery(original, ranking_date="2026-10-05", now="2026-10-09T12:00:00Z")
        with patch("ranking_alerts.incidents.save_incidents", side_effect=StorageError("storage_write_failed")):
            with self.assertRaises(StorageError):
                tx.save_collection(self.rankings, self.state, rankings=self.outcome.rankings,
                                   state=self.outcome.state, incidents_path=incidents_path, incidents=recovered)
        self.assertEqual(original, load_incidents(incidents_path))
        tx.recover_collection(self.rankings, self.state, incidents_path)
        self.assertEqual(recovered, load_incidents(incidents_path))
        self.assertEqual(self.outcome.state, load_alert_state(self.state, self.outcome.rankings))

    def test_second_local_writer_is_rejected_before_processing(self):
        with state_lock(self.state):
            with self.assertRaisesRegex(StorageError, "state_writer_busy"):
                with state_lock(self.state):
                    self.fail("concurrent writer acquired the lock")
        with state_lock(self.state):
            pass


class GitCheckpointTests(unittest.TestCase):
    def git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.remote, self.repo = self.root / "remote.git", self.root / "repo"
        self.git(self.root, "init", "--bare", str(self.remote))
        self.git(self.root, "init", "-b", "main", str(self.repo))
        self.git(self.repo, "config", "user.name", "Test")
        self.git(self.repo, "config", "user.email", "test@example.invalid")
        self.git(self.repo, "remote", "add", "origin", str(self.remote))
        write_json_atomic(self.repo / "data/rankings.json", {"schema_version": 1,
            "player": {"atp_id": "B0UF", "name": "Luka Bojicic Ono"}, "snapshots": []})
        write_json_atomic(self.repo / "automation/state/ranking_alerts.json", {"schema_version": 1, "outbox": []})
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-m", "initial")
        self.git(self.repo, "push", "-u", "origin", "main")

    def test_checkpoint_publishes_the_complete_valid_bundle(self):
        ledger = self.repo / "automation/state/ranking_incidents.json"
        write_json_atomic(ledger, {"schema_version": 1, "atp_id": "B0UF", "events": []})
        GitCheckpoint(self.repo)()
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"),
                         self.git(self.remote, "rev-parse", "refs/heads/main"))
        self.assertEqual(json.loads(ledger.read_text()), json.loads(self.git(self.remote, "show", "main:automation/state/ranking_incidents.json")))

    def test_concurrent_remote_change_fails_without_rebase_or_overwrite(self):
        other = self.root / "other"
        self.git(self.root, "clone", "-b", "main", str(self.remote), str(other))
        self.git(other, "config", "user.name", "Other")
        self.git(other, "config", "user.email", "other@example.invalid")
        (other / "unrelated.txt").write_text("other writer")
        self.git(other, "add", ".")
        self.git(other, "commit", "-m", "other")
        self.git(other, "push")
        remote_head = self.git(self.remote, "rev-parse", "main")
        write_json_atomic(self.repo / "automation/state/ranking_incidents.json",
                          {"schema_version": 1, "atp_id": "B0UF", "events": []})
        with self.assertRaisesRegex(StorageError, "ranking_checkpoint_failed"):
            GitCheckpoint(self.repo)()
        self.assertEqual(remote_head, self.git(self.remote, "rev-parse", "main"))
        self.assertFalse((self.repo / "unrelated.txt").exists())

    def test_unrelated_staged_changes_are_never_committed(self):
        (self.repo / "unrelated.txt").write_text("private local work")
        self.git(self.repo, "add", "unrelated.txt")
        with self.assertRaisesRegex(StorageError, "checkpoint_unrelated_staged_files"):
            GitCheckpoint(self.repo)()

    def test_existing_sporting_storage_error_does_not_prevent_incident_checkpoint(self):
        state = self.repo / "automation/state/ranking_alerts.json"
        state.write_text("corrupt historical sporting state")
        self.git(self.repo, "add", "automation/state/ranking_alerts.json")
        self.git(self.repo, "commit", "-m", "simulate pre-existing storage fault")
        self.git(self.repo, "push")
        write_json_atomic(self.repo / "automation/state/ranking_incidents.json",
                          {"schema_version": 1, "atp_id": "B0UF", "events": []})
        GitCheckpoint(self.repo)()
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), self.git(self.remote, "rev-parse", "main"))

    def test_new_invalid_sporting_state_is_never_published(self):
        before = self.git(self.remote, "rev-parse", "main")
        (self.repo / "automation/state/ranking_alerts.json").write_text("invalid new state")
        with self.assertRaises(StorageError):
            GitCheckpoint(self.repo)()
        self.assertEqual(before, self.git(self.remote, "rev-parse", "main"))

    def test_two_stale_clones_cannot_send_the_same_pending_event(self):
        from ranking_alerts.providers import DeliveryReceipt
        class MockProvider:
            name = "callmebot"
            last_attempt_count = 1
            calls = 0

            def send(self, **kwargs):
                self.calls += 1
                return DeliveryReceipt(provider=self.name, accepted_at="2026-10-06T12:01:00Z", http_status=200)
        observation = RankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
            ranking_date="2026-10-05", singles=DisciplineRanking(rank=2250, points=None),
            doubles=DisciplineRanking(rank=1417, points=None))
        outcome = update_rankings.plan_collection(RankingsData(), RankingAlertState(), observation,
                                                  captured_at="2026-10-06T12:00:00Z")
        ranking_path = self.repo / "data/rankings.json"
        state_path = self.repo / "automation/state/ranking_alerts.json"
        tx.save_collection(ranking_path, state_path, rankings=outcome.rankings, state=outcome.state)
        GitCheckpoint(self.repo)()
        other = self.root / "other"
        self.git(self.root, "clone", "-b", "main", str(self.remote), str(other))
        self.git(other, "config", "user.name", "Other")
        self.git(other, "config", "user.email", "other@example.invalid")
        first, second = MockProvider(), MockProvider()
        self.assertEqual(1, update_rankings.deliver(provider=first, rankings_path=ranking_path,
                                                   state_path=state_path, checkpoint=GitCheckpoint(self.repo)))
        with self.assertRaises(StorageError):
            update_rankings.deliver(provider=second, rankings_path=other / "data/rankings.json",
                state_path=other / "automation/state/ranking_alerts.json", checkpoint=GitCheckpoint(other))
        self.assertEqual(1, first.calls)
        self.assertEqual(0, second.calls)

    def test_durable_cli_rejects_noncanonical_paths_before_constructing_provider(self):
        args = update_rankings.build_parser().parse_args([
            "deliver", "--provider", "callmebot", "--durable-git", "--state-path", str(self.root / "elsewhere.json")])
        with self.assertRaisesRegex(update_rankings.ConfigurationError, "checkpoint_requires_canonical_paths"):
            update_rankings._git_checkpoint(args)


if __name__ == "__main__":
    unittest.main()
