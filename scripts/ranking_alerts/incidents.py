"""Append-only STALE audit ledger, independent of sporting snapshots/outbox."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .providers import ConfigurationError, DeliveryError, NotificationProvider
from .storage import StorageError, _load_json, write_json_atomic

DEFAULT_INCIDENTS_PATH = Path("automation/state/ranking_incidents.json")
KINDS = {"created", "provider_failed", "provider_accepted", "recovered"}


def _date(value: Any) -> str:
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError()
    return value


def _stamp(value: Any) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise ValueError()
    return value


def _time(value: str) -> datetime:
    return datetime.fromisoformat(_stamp(value).replace("Z", "+00:00"))


@dataclass(frozen=True)
class IncidentLedger:
    events: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        created: set[str] = set()
        accepted: set[str] = set()
        recovered: set[str] = set()
        previous: dict[str, dict[str, Any]] = {}
        try:
            for event in self.events:
                if not isinstance(event, dict) or set(event) != {
                    "incident_id", "kind", "at", "expected_date", "last_valid_date",
                    "source", "cutoff_at", "attempts", "error_code", "retryable", "recovery_date",
                }:
                    raise ValueError()
                expected = _date(event["expected_date"])
                if event["incident_id"] != f"ranking_stale:{expected}" or event["kind"] not in KINDS:
                    raise ValueError()
                _stamp(event["at"])
                cutoff = _stamp(event["cutoff_at"])
                if event["last_valid_date"] is not None:
                    _date(event["last_valid_date"])
                if not isinstance(event["source"], str) or not re.fullmatch(r"[a-z0-9-]{1,64}", event["source"]):
                    raise ValueError()
                if type(event["attempts"]) is not int or event["attempts"] < 0 or type(event["retryable"]) is not bool:
                    raise ValueError()
                if event["error_code"] is not None and not re.fullmatch(r"[a-z0-9_]+", event["error_code"]):
                    raise ValueError()
                identity = event["incident_id"]
                prior = previous.get(identity)
                if prior is not None:
                    if any(event[key] != prior[key] for key in ("expected_date", "last_valid_date", "source", "cutoff_at")):
                        raise ValueError()
                    if _time(event["at"]) < _time(prior["at"]) or event["attempts"] < prior["attempts"]:
                        raise ValueError()
                if event["kind"] == "recovered":
                    if _date(event["recovery_date"]) < expected or event["retryable"]:
                        raise ValueError()
                elif event["recovery_date"] is not None:
                    raise ValueError()
                if event["kind"] == "created":
                    if identity in created or _time(event["at"]) < _time(cutoff) or event["attempts"] != 0 or event["error_code"] is not None or not event["retryable"]:
                        raise ValueError()
                    if event["last_valid_date"] is not None and event["last_valid_date"] >= expected:
                        raise ValueError()
                    created.add(identity)
                elif identity not in created or identity in recovered:
                    raise ValueError()
                elif event["kind"] == "provider_accepted":
                    if identity in accepted or not prior["retryable"] or event["retryable"] or event["error_code"] is not None or event["attempts"] <= prior["attempts"]:
                        raise ValueError()
                    accepted.add(identity)
                elif event["kind"] == "provider_failed":
                    if identity in accepted or not prior["retryable"] or event["error_code"] is None or event["attempts"] <= prior["attempts"]:
                        raise ValueError()
                elif event["kind"] == "recovered":
                    recovered.add(identity)
                previous[identity] = event
        except (ValueError, TypeError, KeyError):
            raise StorageError("invalid_incident_ledger") from None

    def latest(self) -> dict[str, dict[str, Any]]:
        return {event["incident_id"]: event for event in self.events}

    def append(self, event: dict[str, Any]) -> "IncidentLedger":
        return IncidentLedger(self.events + (dict(event),))


def load_incidents(path: Path = DEFAULT_INCIDENTS_PATH) -> IncidentLedger:
    if not path.exists():
        return IncidentLedger()
    value = _load_json(path)
    if not isinstance(value, dict) or set(value) != {"schema_version", "atp_id", "events"} or type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["atp_id"] != "B0UF" or not isinstance(value["events"], list):
        raise StorageError("invalid_incident_ledger")
    return IncidentLedger(tuple(value["events"]))


def save_incidents(path: Path, ledger: IncidentLedger) -> None:
    IncidentLedger(ledger.events)
    write_json_atomic(path, {"schema_version": 1, "atp_id": "B0UF", "events": list(ledger.events)})


def plan_stale(ledger: IncidentLedger, *, expected_date: str, last_valid_date: str | None,
               source: str, cutoff_at: str, now: str) -> IncidentLedger:
    identity = f"ranking_stale:{expected_date}"
    if identity in ledger.latest():
        return ledger
    return ledger.append({"incident_id": identity, "kind": "created", "at": now,
                          "expected_date": expected_date, "last_valid_date": last_valid_date,
                          "source": source, "cutoff_at": cutoff_at, "attempts": 0,
                          "error_code": None, "retryable": True, "recovery_date": None})


def plan_recovery(ledger: IncidentLedger, *, ranking_date: str, now: str) -> IncidentLedger:
    for item in ledger.latest().values():
        if item["kind"] != "recovered" and item["expected_date"] <= ranking_date:
            ledger = ledger.append({**item, "kind": "recovered", "at": now,
                                    "retryable": False, "recovery_date": ranking_date})
    return ledger


def pending_incidents(ledger: IncidentLedger) -> tuple[dict[str, Any], ...]:
    return tuple(item for item in ledger.latest().values()
                 if item["kind"] in {"created", "provider_failed"} and item["retryable"])


def format_stale(item: dict[str, Any]) -> str:
    return ("RANKING_STALE — Luka Bojicic Ono (B0UF)\n"
            f"Edição esperada: {item['expected_date']}\n"
            f"Última edição válida: {item['last_valid_date'] or 'não disponível'}\n"
            f"Fonte: {item['source']}\n"
            "A edição esperada ainda não foi confirmada; rankings anteriores não representam dados atuais.")


def deliver_incidents(*, provider: NotificationProvider, path: Path, now: str) -> int:
    if provider.name != "callmebot":
        raise ConfigurationError("invalid_delivery_provider")
    ledger = load_incidents(path)
    count = 0
    for item in pending_incidents(ledger):
        try:
            receipt = provider.send(message=format_stale(item), event_id=item["incident_id"])
            if receipt.provider != "callmebot" or receipt.delivery_status != "provider_accepted":
                raise DeliveryError("provider_response_ambiguous", max(1, getattr(provider, "last_attempt_count", 1)))
        except DeliveryError as exc:
            ledger = ledger.append({**item, "kind": "provider_failed", "at": now,
                                    "attempts": item["attempts"] + exc.attempts,
                                    "error_code": exc.code, "retryable": exc.retryable})
            save_incidents(path, ledger)
            raise
        ledger = ledger.append({**item, "kind": "provider_accepted", "at": receipt.accepted_at,
                                "attempts": item["attempts"] + max(1, getattr(provider, "last_attempt_count", 1)),
                                "error_code": None, "retryable": False})
        save_incidents(path, ledger)
        count += 1
    return count
