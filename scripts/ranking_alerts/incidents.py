"""Append-only operational incidents, independent of sporting snapshots/outbox."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import UUID, uuid4

from .providers import ConfigurationError, DeliveryError, NotificationProvider
from .source import RANKING_SOURCE_ERROR_CODES
from .storage import StorageError, _load_json, write_json_atomic

DEFAULT_INCIDENTS_PATH = Path("automation/state/ranking_incidents.json")
KINDS = {"created", "provider_in_flight", "provider_failed", "provider_accepted", "recovered"}
SOURCE_ERROR_CATEGORIES = {"identity", "http", "timeout", "schema", "unavailable"}
_FIELDS = {"incident_id", "kind", "at", "expected_date", "last_valid_date",
           "source", "cutoff_at", "attempts", "error_code", "retryable", "recovery_date"}
_SOURCE_FIELDS = {"source_error_code", "source_error_category"}
# These outcomes do not establish that a provider did not accept the message.
# Old ledgers containing retryable timeouts also remain quarantined on reload.
_UNCERTAIN_DELIVERY_CODES = {"transport_timeout", "transport_error", "provider_error",
                             "provider_response_ambiguous", "http_408"} | {f"http_{code}" for code in range(500, 600)}
_DELIVERY_CODES = _UNCERTAIN_DELIVERY_CODES | {"provider_application_error", "invalid_message"}


def classify_source_error(code: str, *, telemetry: Any = None) -> str:
    """Classify only stable codes and HTTP statuses; never retain response text."""
    if code == "ranking_source_identity_mismatch":
        return "identity"
    if code == "ranking_source_timeout":
        return "timeout"
    if code in {"ranking_source_schema_changed", "ranking_source_future",
                "ranking_source_edition_invalid", "ranking_source_stale",
                "ranking_source_coverage_truncated"}:
        return "schema"
    if code in {"ranking_source_authentication", "ranking_source_blocked", "ranking_source_rate_limited"}:
        return "http"
    if isinstance(telemetry, Mapping):
        statuses = [telemetry.get("navigation_status")]
        for discipline in ("singles", "doubles"):
            value = telemetry.get(discipline)
            if isinstance(value, Mapping):
                statuses.append(value.get("http_status"))
        if any(type(status) is int and 400 <= status <= 599 for status in statuses):
            return "http"
    return "unavailable"


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
                if not isinstance(event, dict) or set(event) not in (
                    _FIELDS, _FIELDS | _SOURCE_FIELDS, _FIELDS | {"attempt_id"},
                    _FIELDS | _SOURCE_FIELDS | {"attempt_id"},
                ):
                    raise ValueError()
                if "attempt_id" in event:
                    attempt = UUID(event["attempt_id"])
                    if attempt.version != 4 or str(attempt) != event["attempt_id"]:
                        raise ValueError()
                expected = _date(event["expected_date"])
                is_source_error = "source_error_category" in event
                if is_source_error:
                    category = event["source_error_category"]
                    if category not in SOURCE_ERROR_CATEGORIES or event["source_error_code"] not in RANKING_SOURCE_ERROR_CODES:
                        raise ValueError()
                    identity = f"ranking_source_error:{category}:{expected}"
                else:
                    identity = f"ranking_stale:{expected}"
                if event["incident_id"] != identity or event["kind"] not in KINDS:
                    raise ValueError()
                _stamp(event["at"])
                cutoff = _stamp(event["cutoff_at"])
                if event["last_valid_date"] is not None:
                    _date(event["last_valid_date"])
                if not isinstance(event["source"], str) or not re.fullmatch(r"[a-z0-9-]{1,64}", event["source"]):
                    raise ValueError()
                if type(event["attempts"]) is not int or event["attempts"] < 0 or type(event["retryable"]) is not bool:
                    raise ValueError()
                if event["error_code"] is not None and (not isinstance(event["error_code"], str) or not re.fullmatch(r"[a-z0-9_]+", event["error_code"])):
                    raise ValueError()
                prior = previous.get(identity)
                if prior is not None:
                    immutable = ("expected_date", "last_valid_date", "source", "cutoff_at") + (tuple(sorted(_SOURCE_FIELDS)) if is_source_error else ())
                    if (set(event) - {"attempt_id"}) != (set(prior) - {"attempt_id"}) or any(event[key] != prior[key] for key in immutable):
                        raise ValueError()
                    if _time(event["at"]) < _time(prior["at"]) or event["attempts"] < prior["attempts"]:
                        raise ValueError()
                if event["kind"] == "recovered":
                    if _date(event["recovery_date"]) < expected or event["retryable"] or event["attempts"] != prior["attempts"] or event.get("attempt_id") != prior.get("attempt_id"):
                        raise ValueError()
                elif event["recovery_date"] is not None:
                    raise ValueError()
                if event["kind"] == "created":
                    if identity in created or "attempt_id" in event or event["attempts"] != 0 or event["error_code"] is not None or not event["retryable"]:
                        raise ValueError()
                    if not is_source_error and (_time(event["at"]) < _time(cutoff) or (event["last_valid_date"] is not None and event["last_valid_date"] >= expected)):
                        raise ValueError()
                    created.add(identity)
                elif identity not in created or identity in recovered:
                    raise ValueError()
                elif event["kind"] == "provider_in_flight":
                    if identity in accepted or not prior["retryable"] or prior["kind"] not in {"created", "provider_failed"} or event["retryable"] or event["error_code"] is not None or event["attempts"] != prior["attempts"] + 1 or event.get("attempt_id") == prior.get("attempt_id"):
                        raise ValueError()
                elif event["kind"] in {"provider_accepted", "provider_failed"}:
                    in_flight = prior["kind"] == "provider_in_flight"
                    # Direct result transitions remain valid for legacy v1 ledgers.
                    if identity in accepted or (not in_flight and (not prior["retryable"] or event["attempts"] <= prior["attempts"])):
                        raise ValueError()
                    if event.get("attempt_id") != prior.get("attempt_id"):
                        raise ValueError()
                    if event["kind"] == "provider_accepted":
                        if event["retryable"] or event["error_code"] is not None:
                            raise ValueError()
                        accepted.add(identity)
                    elif event["error_code"] is None:
                        raise ValueError()
                    elif in_flight and event["retryable"] and event["error_code"] in _UNCERTAIN_DELIVERY_CODES:
                        raise ValueError()
                elif event["kind"] == "recovered":
                    recovered.add(identity)
                previous[identity] = event
        except (ValueError, TypeError, KeyError, AttributeError):
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
    if path.exists():
        previous = load_incidents(path)
        if ledger.events[:len(previous.events)] != previous.events:
            raise StorageError("incident_ledger_not_append_only")
        if previous == ledger:
            return
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


def plan_source_error(ledger: IncidentLedger, *, expected_date: str, last_valid_date: str | None,
                      source: str, cutoff_at: str, now: str, error_code: str,
                      telemetry: Any = None) -> IncidentLedger:
    if not isinstance(error_code, str) or error_code not in RANKING_SOURCE_ERROR_CODES:
        raise StorageError("invalid_source_error_code")
    category = classify_source_error(error_code, telemetry=telemetry)
    identity = f"ranking_source_error:{category}:{expected_date}"
    if identity in ledger.latest():
        return ledger
    return ledger.append({"incident_id": identity, "kind": "created", "at": now,
                          "expected_date": expected_date, "last_valid_date": last_valid_date,
                          "source": source, "cutoff_at": cutoff_at, "attempts": 0,
                          "error_code": None, "retryable": True, "recovery_date": None,
                          "source_error_code": error_code, "source_error_category": category})


def plan_recovery(ledger: IncidentLedger, *, ranking_date: str, now: str) -> IncidentLedger:
    for item in ledger.latest().values():
        if item["kind"] != "recovered" and item["expected_date"] <= ranking_date:
            ledger = ledger.append({**item, "kind": "recovered", "at": now,
                                    "retryable": False, "recovery_date": ranking_date})
    return ledger


def pending_incidents(ledger: IncidentLedger) -> tuple[dict[str, Any], ...]:
    return tuple(item for item in ledger.latest().values()
                 if item["kind"] in {"created", "provider_failed"} and item["retryable"]
                 and item["error_code"] in {None, "http_429"})


def unresolved_deliveries(ledger: IncidentLedger) -> tuple[dict[str, Any], ...]:
    """Source recovery is not reconciliation of an uncertain provider attempt.

    Read the last delivery transition independently from the source lifecycle.
    This also preserves quarantine for legacy retryable timeout/5xx records.
    A recovered, definitely rejected 429 does not need delivery reconciliation.
    """
    latest = {}
    for event in ledger.events:
        if event["kind"].startswith("provider_"):
            latest[event["incident_id"]] = event
    return tuple(event for event in latest.values()
                 if event["kind"] == "provider_in_flight"
                 or (event["kind"] == "provider_failed"
                     and not (event["retryable"] and event["error_code"] == "http_429")))


def format_stale(item: dict[str, Any]) -> str:
    return ("RANKING_STALE — Luka Bojicic Ono (B0UF)\n"
            f"Edição esperada: {item['expected_date']}\n"
            f"Última edição válida: {item['last_valid_date'] or 'não disponível'}\n"
            f"Fonte: {item['source']}\n"
            "A edição esperada ainda não foi confirmada; rankings anteriores não representam dados atuais.")


def format_incident(item: dict[str, Any]) -> str:
    if "source_error_category" not in item:
        return format_stale(item)
    return ("SOURCE_ERROR — Luka Bojicic Ono (B0UF)\n"
            f"Edição esperada: {item['expected_date']}\n"
            f"Última edição válida: {item['last_valid_date'] or 'não disponível'}\n"
            f"Fonte: {item['source']}\n"
            f"Falha: {item['source_error_category']} ({item['source_error_code']})\n"
            "A fonte não forneceu uma observação válida; a atualização está bloqueada.")


def _attempt_count(provider: NotificationProvider) -> int:
    value = getattr(provider, "last_attempt_count", 1)
    return value if type(value) is int and value > 0 else 1


def _checkpoint(callback: Callable[[], None] | None) -> None:
    if callback is not None:
        try:
            callback()
        except Exception:
            raise StorageError("incident_checkpoint_failed") from None


def deliver_incidents(*, provider: NotificationProvider, path: Path, now: str,
                      checkpoint: Callable[[], None] | None = None) -> int:
    """Persist a claim before every send and checkpoint each durable transition.

    An interrupted/uncertain claim is quarantined, never automatically replayed.
    A failed checkpoint aborts delivery. Independent provider failures do not
    prevent processing other incidents; the first failure is raised afterward.
    """
    if provider.name != "callmebot":
        raise ConfigurationError("invalid_delivery_provider")
    ledger = load_incidents(path)
    count = 0
    first_error: DeliveryError | StorageError | None = None
    for item in pending_incidents(ledger):
        # Reload after each result so a failed write cannot cause a later save
        # to erase another durable event or conceal an uncertain outcome.
        ledger = load_incidents(path)
        in_flight = {**item, "kind": "provider_in_flight", "at": now,
                     "attempts": item["attempts"] + 1, "error_code": None, "retryable": False,
                     "attempt_id": str(uuid4())}
        try:
            ledger = ledger.append(in_flight)
            save_incidents(path, ledger)
        except StorageError as exc:
            raise
        _checkpoint(checkpoint)
        try:
            receipt = provider.send(message=format_incident(item), event_id=item["incident_id"])
            if receipt.provider != "callmebot" or receipt.delivery_status != "provider_accepted":
                raise DeliveryError("provider_response_ambiguous", _attempt_count(provider))
            _stamp(receipt.accepted_at)
            if _time(receipt.accepted_at) < _time(now):
                raise DeliveryError("provider_response_ambiguous", _attempt_count(provider))
        except Exception as exc:
            if not isinstance(exc, DeliveryError):
                exc = DeliveryError("provider_error", _attempt_count(provider))
            # No arbitrary exception text/code is retained in the audit file.
            code = exc.code if isinstance(exc.code, str) and (exc.code in _DELIVERY_CODES or re.fullmatch(r"http_[1-5][0-9]{2}", exc.code)) else "provider_error"
            attempts = exc.attempts if type(exc.attempts) is int and exc.attempts > 0 else 1
            result = {**in_flight, "kind": "provider_failed", "at": now,
                      "attempts": item["attempts"] + attempts, "error_code": code,
                      "retryable": bool(exc.retryable) and code == "http_429"}
            first_error = first_error or DeliveryError(code, attempts, retryable=result["retryable"])
        else:
            result = {**in_flight, "kind": "provider_accepted", "at": receipt.accepted_at,
                      "attempts": item["attempts"] + _attempt_count(provider)}
        try:
            save_incidents(path, ledger.append(result))
        except StorageError as exc:
            raise
        _checkpoint(checkpoint)
        if result["kind"] == "provider_accepted":
            count += 1
    if first_error is not None:
        raise first_error
    return count
