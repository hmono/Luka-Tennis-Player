"""Append-only, sanitized collection provenance and incident episode history."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .storage import StorageError, _load_json, write_json_atomic

DEFAULT_RUNTIME_PATH = Path("automation/state/ranking_runtime.json")


def load_runtime(path: Path) -> dict[str, Any]:
    value = _load_json(path) if path.exists() else {"schema_version": 1, "events": []}
    try:
        if set(value) != {"schema_version", "events"} or type(value["schema_version"]) is not int or value["schema_version"] != 1 or not isinstance(value["events"], list):
            raise ValueError()
        prior = None
        for entry in value["events"]:
            if set(entry) != {"at", "state", "last_valid_date", "error_code", "provenance"}:
                raise ValueError()
            at = datetime.fromisoformat(entry["at"].replace("Z", "+00:00"))
            if not entry["at"].endswith("Z") or (prior and at < prior):
                raise ValueError()
            prior = at
            if entry["state"] not in {"FRESH", "NO_NEW_EDITION_OBSERVED", "SOURCE_ERROR"} or not isinstance(entry["provenance"], dict):
                raise ValueError()
            if entry["last_valid_date"] is not None:
                from .domain import _iso_date
                _iso_date(entry["last_valid_date"])
            if entry["error_code"] is not None:
                import re
                if not isinstance(entry["error_code"], str) or not re.fullmatch(r"[a-z0-9_]+", entry["error_code"]):
                    raise ValueError()
        return value
    except (ValueError, TypeError, KeyError, AttributeError):
        raise StorageError("invalid_ranking_runtime") from None


def append_cycle(path: Path, *, at: str, state: str, last_valid_date: str | None,
                 error_code: str | None, provenance: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    value = load_runtime(path)
    previous = value["events"][-1] if value["events"] else None
    episode = None
    if state == "SOURCE_ERROR":
        start = len(value["events"])
        while start and value["events"][start - 1]["state"] == "SOURCE_ERROR":
            start -= 1
        episode = f"source-error:{start}"
    elif previous and previous["state"] == "SOURCE_ERROR":
        start = len(value["events"])
        while start and value["events"][start - 1]["state"] == "SOURCE_ERROR":
            start -= 1
        episode = f"source-recovered:{start}"
    value["events"].append({"at": at, "state": state, "last_valid_date": last_valid_date,
                            "error_code": error_code, "provenance": provenance})
    write_json_atomic(path, value)
    load_runtime(path)
    return value, episode
