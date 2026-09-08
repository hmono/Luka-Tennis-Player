"""Validated, atomic JSON persistence for rankings and notification state."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .domain import (
    DomainValidationError,
    RankingAlertState,
    RankingsData,
    rankings_from_dict,
    rankings_to_dict,
    state_from_dict,
    state_to_dict,
)


class StorageError(RuntimeError):
    """A storage failure with a redacted, stable error code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageError("invalid_json_storage") from exc


def load_rankings(path: str | os.PathLike[str]) -> RankingsData:
    target = Path(path)
    if not target.exists():
        return RankingsData()
    try:
        return rankings_from_dict(_load_json(target))
    except DomainValidationError as exc:
        raise StorageError(exc.code) from exc


def _outbox_sort_key(item: object, ranking_dates: dict[str, str]) -> tuple[str, str, str]:
    snapshot_id = getattr(item, "snapshot_id")
    return ranking_dates[snapshot_id], getattr(item, "created_at"), getattr(item, "id")


def load_alert_state(
    path: str | os.PathLike[str],
    rankings: RankingsData,
) -> RankingAlertState:
    target = Path(path)
    if not target.exists():
        return RankingAlertState()
    try:
        state = state_from_dict(_load_json(target))
    except DomainValidationError as exc:
        raise StorageError(exc.code) from exc

    ranking_dates = {snapshot.id: snapshot.ranking_date for snapshot in rankings.snapshots}
    if any(item.snapshot_id not in ranking_dates for item in state.outbox):
        raise StorageError("invalid_snapshot_reference")
    if tuple(sorted(state.outbox, key=lambda item: _outbox_sort_key(item, ranking_dates))) != state.outbox:
        raise StorageError("invalid_outbox_order")
    return state


def write_json_atomic(path: str | os.PathLike[str], payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = handle.name
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
        temp_path = None
        try:
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # Directory fsync is not supported on every platform/filesystem.
            pass
    except OSError as exc:
        raise StorageError("storage_write_failed") from exc
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def save_rankings(path: str | os.PathLike[str], data: RankingsData) -> None:
    # Round-trip validation prevents serializing an invalid in-memory object.
    rankings_from_dict(rankings_to_dict(data))
    write_json_atomic(path, rankings_to_dict(data))


def save_alert_state(
    path: str | os.PathLike[str],
    state: RankingAlertState,
    rankings: RankingsData | None = None,
) -> None:
    state_from_dict(state_to_dict(state))
    if rankings is not None:
        ranking_dates = {snapshot.id: snapshot.ranking_date for snapshot in rankings.snapshots}
        if any(item.snapshot_id not in ranking_dates for item in state.outbox):
            raise StorageError("invalid_snapshot_reference")
        if tuple(sorted(state.outbox, key=lambda item: _outbox_sort_key(item, ranking_dates))) != state.outbox:
            raise StorageError("invalid_outbox_order")
    write_json_atomic(path, state_to_dict(state))
