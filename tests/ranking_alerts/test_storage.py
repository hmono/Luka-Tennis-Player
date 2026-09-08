from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ranking_alerts.domain import (
    DisciplineRanking,
    OutboxItem,
    RankingAlertState,
    RankingObservation,
    RankingsData,
    build_snapshot,
    event_id,
    rankings_to_dict,
    state_to_dict,
)
from scripts.ranking_alerts.storage import (
    StorageError,
    load_alert_state,
    load_rankings,
    save_alert_state,
    save_rankings,
    write_json_atomic,
)


def make_snapshot(ranking_date: str, captured_at: str, rank: int):
    observation = RankingObservation(
        atp_id="B0UF",
        name="Luka Bojicic Ono",
        ranking_date=ranking_date,
        singles=DisciplineRanking(rank=rank, points=5, career_high_rank=rank),
        doubles=DisciplineRanking(rank=1800, points=6, career_high_rank=1700),
    )
    return build_snapshot(observation, captured_at=captured_at)


def make_item(snapshot, created_at: str) -> OutboxItem:
    return OutboxItem(
        id=event_id(snapshot.id, "ranking_change"),
        snapshot_id=snapshot.id,
        event_type="ranking_change",
        status="pending",
        attempts=0,
        created_at=created_at,
        sent_at=None,
        provider="callmebot",
        last_error_code=None,
    )


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.rankings_path = self.root / "data" / "rankings.json"
        self.state_path = self.root / "automation" / "state" / "ranking_alerts.json"

    def test_missing_files_load_as_empty_bootstrap_state(self) -> None:
        rankings = load_rankings(self.rankings_path)
        state = load_alert_state(self.state_path, rankings)

        self.assertEqual((), rankings.snapshots)
        self.assertEqual((), state.outbox)
        self.assertFalse(self.rankings_path.exists())
        self.assertFalse(self.state_path.exists())

    def test_save_creates_parent_directories_and_round_trips(self) -> None:
        current = make_snapshot("2026-09-01", "2026-09-01T12:00:00Z", 1973)
        rankings = RankingsData(snapshots=(current,))
        state = RankingAlertState(outbox=(make_item(current, "2026-09-01T12:00:00Z"),))

        save_rankings(self.rankings_path, rankings)
        save_alert_state(self.state_path, state)

        self.assertEqual(rankings, load_rankings(self.rankings_path))
        self.assertEqual(state, load_alert_state(self.state_path, rankings))

    def test_atomic_write_replaces_target_with_complete_json(self) -> None:
        self.rankings_path.parent.mkdir(parents=True)
        self.rankings_path.write_text('{"old": true}\n', encoding="utf-8")
        replacements: list[tuple[Path, Path]] = []

        from scripts.ranking_alerts import storage

        real_replace = storage.os.replace

        def recording_replace(source, target):
            replacements.append((Path(source), Path(target)))
            return real_replace(source, target)

        with patch("scripts.ranking_alerts.storage.os.replace", side_effect=recording_replace):
            write_json_atomic(self.rankings_path, {"schema_version": 1, "snapshots": []})

        self.assertEqual(self.rankings_path, replacements[0][1])
        self.assertNotEqual(self.rankings_path, replacements[0][0])
        self.assertEqual(
            {"schema_version": 1, "snapshots": []},
            json.loads(self.rankings_path.read_text(encoding="utf-8")),
        )

    def test_replace_failure_preserves_existing_target(self) -> None:
        self.rankings_path.parent.mkdir(parents=True)
        original = '{"old": true}\n'
        self.rankings_path.write_text(original, encoding="utf-8")

        with patch(
            "scripts.ranking_alerts.storage.os.replace",
            side_effect=OSError("simulated replace failure"),
        ):
            with self.assertRaises(StorageError):
                write_json_atomic(self.rankings_path, {"new": True})

        self.assertEqual(original, self.rankings_path.read_text(encoding="utf-8"))

    def test_invalid_json_fails_closed(self) -> None:
        self.rankings_path.parent.mkdir(parents=True)
        self.rankings_path.write_text("not-json", encoding="utf-8")

        with self.assertRaises(StorageError):
            load_rankings(self.rankings_path)

    def test_load_rejects_dangling_outbox_reference(self) -> None:
        rankings = RankingsData()
        self.state_path.parent.mkdir(parents=True)
        payload = {
            "schema_version": 1,
            "outbox": [
                {
                    "id": "sha256:" + "a" * 64,
                    "snapshot_id": "sha256:" + "b" * 64,
                    "event_type": "ranking_change",
                    "status": "pending",
                    "attempts": 0,
                    "created_at": "2026-09-01T12:00:00Z",
                    "sent_at": None,
                    "provider": "callmebot",
                    "last_error_code": None,
                }
            ],
        }
        self.state_path.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaises(StorageError):
            load_alert_state(self.state_path, rankings)

    def test_load_rejects_snapshots_out_of_chronological_order(self) -> None:
        older = make_snapshot("2026-09-01", "2026-09-01T12:00:00Z", 1973)
        newer = make_snapshot("2026-09-08", "2026-09-08T12:00:00Z", 1960)
        payload = rankings_to_dict(RankingsData(snapshots=(older, newer)))
        payload["snapshots"].reverse()
        self.rankings_path.parent.mkdir(parents=True)
        self.rankings_path.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaises(StorageError):
            load_rankings(self.rankings_path)

    def test_load_rejects_outbox_out_of_fifo_order(self) -> None:
        older = make_snapshot("2026-09-01", "2026-09-01T12:00:00Z", 1973)
        newer = make_snapshot("2026-09-08", "2026-09-08T12:00:00Z", 1960)
        rankings = RankingsData(snapshots=(older, newer))
        state = RankingAlertState(
            outbox=(
                make_item(older, "2026-09-01T12:00:00Z"),
                make_item(newer, "2026-09-08T12:00:00Z"),
            )
        )
        payload = state_to_dict(state)
        payload["outbox"].reverse()
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaises(StorageError):
            load_alert_state(self.state_path, rankings)


if __name__ == "__main__":
    unittest.main()
