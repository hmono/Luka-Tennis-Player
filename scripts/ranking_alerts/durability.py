"""Serialize local writers and checkpoint delivery reservations in Git.

A successful push is required before any external delivery. An interrupted or
ambiguous attempt remains reserved for operator review, never automatic replay.
Git failures are deliberately not rebased: another writer must not invalidate
the state on which a notification decision was made.
"""

from __future__ import annotations

import fcntl
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .storage import StorageError

STATE_PATHS = (
    "data/rankings.json",
    "automation/state/ranking_alerts.json",
    "automation/state/ranking_incidents.json",
)


@contextmanager
def state_lock(state_path: Path) -> Iterator[None]:
    """Linux/Actions advisory lock, held across read/plan/persist/send."""
    lock = state_path.parent / ".ranking-state.lock"
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        handle = lock.open("a")
    except OSError:
        raise StorageError("state_lock_failed") from None
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise StorageError("state_writer_busy") from None
        yield
    finally:
        handle.close()


class GitCheckpoint:
    """Commit only ranking state, then push without merging remote changes."""

    def __init__(self, root: Path, *, branch: str = "main") -> None:
        self.root = root.resolve()
        self.branch = branch
        if self._git("check-ref-format", "--branch", branch) != branch:
            raise StorageError("checkpoint_invalid_branch")
        if self._git("rev-parse", "--show-toplevel") != str(self.root):
            raise StorageError("checkpoint_invalid_repository")
        if self._git("branch", "--show-current") != branch:
            raise StorageError("checkpoint_wrong_branch")

    def _git(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args], cwd=self.root, check=True, capture_output=True,
                text=True, timeout=90,
            )
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            # Git errors may contain authenticated remote URLs. Never echo them.
            raise StorageError("ranking_checkpoint_failed") from None

    def __call__(self) -> None:
        from .collection_transaction import recover_collection
        from .storage import load_alert_state, load_rankings
        from .incidents import load_incidents

        recover_collection(self.root / STATE_PATHS[0], self.root / STATE_PATHS[1])
        # An unchanged, pre-existing sporting storage error must not suppress
        # an independent source incident. Never publish a newly invalid pair.
        if self._git("status", "--porcelain", "--", *STATE_PATHS[:2]):
            load_alert_state(self.root / STATE_PATHS[1], load_rankings(self.root / STATE_PATHS[0]))
        load_incidents(self.root / STATE_PATHS[2])
        staged = set(self._git("diff", "--cached", "--name-only").splitlines())
        if staged - set(STATE_PATHS):
            raise StorageError("checkpoint_unrelated_staged_files")
        existing = [name for name in STATE_PATHS if (self.root / name).is_file()]
        if existing:
            self._git("add", "--", *existing)
        if self._git("diff", "--cached", "--name-only"):
            self._git("commit", "-m", "data: checkpoint ranking notification state [automated]")
        # Even with no diff, an earlier failed push may have left a local commit.
        self._git("push", "origin", f"HEAD:refs/heads/{self.branch}")
