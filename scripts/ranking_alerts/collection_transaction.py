"""Recoverable local transaction for the sporting snapshot/outbox pair.

The journal precedes both writes. Replay accepts only the original or planned
content, so it cannot roll back receipts or overwrite a concurrent collection.
Git publishes the validated pair together; this local journal is never history.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .domain import RankingsData, RankingAlertState, rankings_to_dict, state_to_dict
from .storage import (
    StorageError, _load_json, load_alert_state, load_rankings,
    save_alert_state, save_rankings, write_json_atomic,
)


def journal_path(state_path: Path) -> Path:
    return state_path.with_name(f".{state_path.name}.collection-pending.json")


def _current(path: Path) -> Any:
    return _load_json(path) if path.exists() else None


def recover_collection(rankings_path: Path, state_path: Path, incidents_path: Path | None = None) -> None:
    path = journal_path(state_path)
    if not path.exists():
        return
    try:
        value = _load_json(path)
        required = {"schema_version", "rankings_path", "state_path", "before", "after"}
        if not isinstance(value, dict) or not required.issubset(value) or set(value) - required - {"incidents_path"} or type(value["schema_version"]) is not int or value["schema_version"] != 1:
            raise ValueError()
        if value["rankings_path"] != str(rankings_path.resolve()) or value["state_path"] != str(state_path.resolve()):
            raise ValueError()
        from .domain import rankings_from_dict, state_from_dict
        rankings = rankings_from_dict(value["after"]["rankings"])
        state = state_from_dict(value["after"]["state"])
        targets = [("rankings", rankings_path), ("state", state_path)]
        if "incidents_path" in value:
            incidents_path = incidents_path or state_path.parent / "ranking_incidents.json"
            if value["incidents_path"] != str(incidents_path.resolve()):
                raise ValueError()
            from .incidents import IncidentLedger
            incidents = IncidentLedger(tuple(value["after"]["incidents"]["events"]))
            targets.append(("incidents", incidents_path))
        for name, target in targets:
            if _current(target) not in (value["before"][name], value["after"][name]):
                raise StorageError("collection_transaction_conflict")
        # Validate references before writing either target.
        ids = {snapshot.id for snapshot in rankings.snapshots}
        if any(item.snapshot_id not in ids for item in state.outbox):
            raise ValueError()
        save_rankings(rankings_path, rankings)
        save_alert_state(state_path, state, rankings)
        if "incidents_path" in value:
            from .incidents import save_incidents
            save_incidents(incidents_path, incidents)
        load_alert_state(state_path, load_rankings(rankings_path))
        path.unlink()
    except StorageError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise StorageError("invalid_collection_transaction") from None


def save_collection(rankings_path: Path, state_path: Path, *, rankings: RankingsData,
                    state: RankingAlertState, incidents_path: Path | None = None,
                    incidents: Any = None) -> None:
    recover_collection(rankings_path, state_path, incidents_path)
    value = {
        "schema_version": 1,
        "rankings_path": str(rankings_path.resolve()),
        "state_path": str(state_path.resolve()),
        "before": {"rankings": _current(rankings_path), "state": _current(state_path)},
        "after": {"rankings": rankings_to_dict(rankings), "state": state_to_dict(state)},
    }
    if incidents_path is not None:
        from .incidents import IncidentLedger
        IncidentLedger(incidents.events)
        value["incidents_path"] = str(incidents_path.resolve())
        value["before"]["incidents"] = _current(incidents_path)
        value["after"]["incidents"] = {"schema_version": 1, "atp_id": "B0UF", "events": list(incidents.events)}
    write_json_atomic(journal_path(state_path), value)
    recover_collection(rankings_path, state_path, incidents_path)
