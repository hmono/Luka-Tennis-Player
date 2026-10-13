"""Durable autonomous delivery; caller holds the shared ranking state_lock.

Remote checkpoint precedes every external effect. Unknown outcomes automatically
finish with possible loss, never replay: CallMeBot offers no idempotency/status
contract. The independent operational sink has its own durable intentions.
Historical sporting outbox and receipts are read, never rewritten.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from .domain import RankingAlertState, RankingsData
from .providers import DeliveryError, NotificationProvider
from .storage import StorageError, _load_json, write_json_atomic

DEFAULT_DELIVERY_PATH = Path("automation/state/ranking_delivery.json")
_TERMINAL = {"provider_accepted", "delivery_unknown", "rejected", "suppressed"}
_STATES = {"planned", "reserved", "retry_wait"} | _TERMINAL
_FIELDS = {"event_id", "channel", "event_type", "state", "at", "message", "metadata",
           "attempts", "attempt_id", "provider", "error_code", "next_attempt_at",
           "risk", "http_status", "delivered_to_device"}
_SAFE_ERRORS = {"transport_timeout", "transport_error", "provider_error",
                "provider_response_ambiguous", "provider_application_error", "invalid_message",
                "ops_sink_unavailable"}
_META = {"snapshot_id", "ranking_date", "period", "last_verified_date", "checked_at",
         "status", "legacy_event_id", "legacy_attempt_id"}


def _time(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError()
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.utcoffset() != timedelta(0):
        raise ValueError()
    return parsed


def _date(value: str) -> str:
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError()
    return value


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _period(now: str) -> str:
    local = _time(now).astimezone(ZoneInfo("America/Sao_Paulo"))
    anchor = (local - timedelta(days=local.weekday())).replace(hour=9, minute=0, second=0, microsecond=0)
    if local < anchor:
        anchor -= timedelta(days=7)
    return anchor.date().isoformat()


@dataclass(frozen=True)
class DeliveryLedger:
    events: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        previous: dict[str, dict[str, Any]] = {}
        try:
            for event in self.events:
                if not isinstance(event, dict) or set(event) != _FIELDS:
                    raise ValueError()
                identity = event["event_id"]
                if not isinstance(identity, str) or not re.fullmatch(r"[a-zA-Z0-9_:.\-]{1,200}", identity):
                    raise ValueError()
                if event["channel"] not in {"sporting", "operational"} or event["event_type"] not in {"edition_digest", "weekly_status", "operational"} or event["state"] not in _STATES:
                    raise ValueError()
                if (event["channel"] == "operational") != (event["event_type"] == "operational"):
                    raise ValueError()
                _time(event["at"])
                if not isinstance(event["message"], str) or not event["message"].strip() or len(event["message"]) > 12000:
                    raise ValueError()
                metadata = event["metadata"]
                if not isinstance(metadata, dict) or set(metadata) - _META:
                    raise ValueError()
                for key, value in metadata.items():
                    if value is not None and not isinstance(value, str):
                        raise ValueError()
                    if key in {"ranking_date", "period", "last_verified_date"} and value is not None:
                        _date(value)
                    if key == "checked_at":
                        _time(value)
                if event["event_type"] == "edition_digest":
                    _date(metadata["ranking_date"])
                    _date(metadata["period"])
                    if not re.fullmatch(r"sha256:[0-9a-f]{64}", metadata.get("snapshot_id", "")) or not re.fullmatch(r"edition:" + re.escape(metadata["ranking_date"]) + r"(?::[0-9a-f]{64}:[1-9][0-9]*)?", identity):
                        raise ValueError()
                if event["event_type"] == "weekly_status":
                    _time(metadata["checked_at"])
                    if date.fromisoformat(metadata["period"]).weekday() != 0 or identity != f"status:{metadata['period']}":
                        raise ValueError()
                    if _time(metadata["checked_at"]).date() < date.fromisoformat(metadata["period"]):
                        raise ValueError()
                if type(event["attempts"]) is not int or event["attempts"] < 0 or type(event["delivered_to_device"]) is not bool or event["delivered_to_device"]:
                    raise ValueError()
                if event["attempt_id"] is not None and not re.fullmatch(r"[0-9a-f]{32}", event["attempt_id"]):
                    raise ValueError()
                if event["provider"] is not None and not re.fullmatch(r"[a-z0-9-]{1,64}", event["provider"]):
                    raise ValueError()
                if event["error_code"] is not None and not re.fullmatch(r"[a-z0-9_]{1,100}", event["error_code"]):
                    raise ValueError()
                if event["http_status"] is not None and (type(event["http_status"]) is not int or not 100 <= event["http_status"] <= 599):
                    raise ValueError()
                if event["risk"] not in {None, "possible_loss"}:
                    raise ValueError()
                if (event["state"] == "delivery_unknown") != (event["risk"] == "possible_loss"):
                    raise ValueError()
                if (event["state"] == "retry_wait") != (event["next_attempt_at"] is not None):
                    raise ValueError()
                if event["next_attempt_at"] is not None and _time(event["next_attempt_at"]) < _time(event["at"]):
                    raise ValueError()
                prior = previous.get(identity)
                if prior is None:
                    if event["state"] != "planned" or event["attempts"] != 0 or event["attempt_id"] is not None:
                        raise ValueError()
                else:
                    if any(event[key] != prior[key] for key in ("event_id", "channel", "event_type", "message", "metadata")) or _time(event["at"]) < _time(prior["at"]) or prior["state"] in _TERMINAL:
                        raise ValueError()
                    if event["state"] == "reserved":
                        if prior["state"] not in {"planned", "retry_wait"} or event["attempts"] != prior["attempts"] + 1 or event["attempt_id"] is None or event["attempt_id"] == prior["attempt_id"]:
                            raise ValueError()
                    else:
                        if event["attempts"] != prior["attempts"] or event["attempt_id"] != prior["attempt_id"]:
                            raise ValueError()
                        if prior["state"] == "reserved" and event["state"] not in {"provider_accepted", "delivery_unknown", "rejected", "retry_wait"}:
                            raise ValueError()
                        if event["state"] == "provider_accepted" and prior["state"] != "reserved" and not metadata.get("legacy_event_id"):
                            raise ValueError()
                        if prior["state"] in {"planned", "retry_wait"} and event["state"] not in _TERMINAL:
                            raise ValueError()
                        if event["state"] == "retry_wait" and event["error_code"] not in {"http_429", "ops_sink_unavailable", "interrupted_ops_attempt"}:
                            raise ValueError()
                previous[identity] = event
            edition_claims: set[str] = set()
            for item in previous.values():
                if item["event_type"] == "edition_digest" and item["state"] not in {"suppressed", "rejected"}:
                    edition = item["metadata"]["ranking_date"]
                    if edition in edition_claims:
                        raise ValueError()
                    edition_claims.add(edition)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise StorageError("invalid_delivery_ledger") from None

    def latest(self) -> dict[str, dict[str, Any]]:
        return {event["event_id"]: event for event in self.events}

    def append(self, event: dict[str, Any]) -> "DeliveryLedger":
        return DeliveryLedger(self.events + (dict(event),))


def load_delivery(path: Path = DEFAULT_DELIVERY_PATH) -> DeliveryLedger:
    if not path.exists():
        return DeliveryLedger()
    value = _load_json(path)
    if not isinstance(value, dict) or set(value) != {"schema_version", "atp_id", "events"} or type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["atp_id"] != "B0UF" or not isinstance(value["events"], list):
        raise StorageError("invalid_delivery_ledger")
    return DeliveryLedger(tuple(value["events"]))


def save_delivery(path: Path, ledger: DeliveryLedger) -> None:
    DeliveryLedger(ledger.events)
    if path.exists():
        previous = load_delivery(path)
        if ledger.events[:len(previous.events)] != previous.events:
            raise StorageError("delivery_ledger_not_append_only")
        if previous == ledger:
            return
    write_json_atomic(path, {"schema_version": 1, "atp_id": "B0UF", "events": list(ledger.events)})


def _plan(ledger: DeliveryLedger, *, identity: str, event_type: str, message: str,
          metadata: dict[str, Any], now: str) -> DeliveryLedger:
    if identity in ledger.latest():
        return ledger
    return ledger.append({"event_id": identity, "channel": "operational" if event_type == "operational" else "sporting",
                          "event_type": event_type, "state": "planned", "at": now,
                          "message": message, "metadata": metadata, "attempts": 0,
                          "attempt_id": None, "provider": None, "error_code": None,
                          "next_attempt_at": None, "risk": None, "http_status": None,
                          "delivered_to_device": False})


def _transition(ledger: DeliveryLedger, item: dict[str, Any], *, state: str, now: str,
                **changes: Any) -> DeliveryLedger:
    return ledger.append({**item, "state": state, "at": now, "next_attempt_at": None,
                          **changes})


def plan_operational(ledger: DeliveryLedger, *, event_id: str, message: str, now: str) -> DeliveryLedger:
    return _plan(ledger, identity="ops:" + hashlib.sha256(event_id.encode()).hexdigest(),
                 event_type="operational", message=message, metadata={}, now=now)


def _alert(ledger: DeliveryLedger, item: dict[str, Any], now: str) -> DeliveryLedger:
    return plan_operational(ledger, event_id=f"delivery:{item['event_id']}:{item['state']}",
                            message=f"ATP delivery {item['state']}: {item['event_id']}; "
                                    f"code={item['error_code'] or 'unknown'}; device delivery unknown. "
                                    "Automatic at-most-once policy: possible loss; no ambiguous replay.", now=now)


def plan_digest(ledger: DeliveryLedger, *, snapshot_id: str, ranking_date: str,
                message: str, now: str, legacy_state: RankingAlertState | None = None,
                legacy_rankings: RankingsData | None = None) -> DeliveryLedger:
    identity = f"edition:{ranking_date}"
    existing = tuple(item for item in ledger.latest().values()
                     if item["event_type"] == "edition_digest" and item["metadata"]["ranking_date"] == ranking_date)
    # A receipt or an uncertain external effect permanently fences this edition.
    # Source revisions may replace only definitely unsent/rejected intentions.
    if any(item["state"] in {"provider_accepted", "delivery_unknown", "reserved"} for item in existing):
        return ledger
    active = next((item for item in existing if item["state"] in {"planned", "retry_wait"}), None)
    if active is not None and active["metadata"]["snapshot_id"] == snapshot_id:
        return ledger
    if existing and active is None:
        return ledger
    if active is not None:
        ledger = _transition(ledger, active, state="suppressed", now=now, error_code="superseded_revision")
        identity = f"edition:{ranking_date}:{snapshot_id[7:]}:{len(existing)}"
    legacy_ids = {snapshot_id}
    if legacy_rankings is not None:
        legacy_ids.update(snapshot.id for snapshot in legacy_rankings.snapshots if snapshot.ranking_date == ranking_date)
    old = tuple(item for item in (legacy_state.outbox if legacy_state else ())
                if item.snapshot_id in legacy_ids and item.event_type in {"weekly_digest", "ranking_change", "ranking_correction"})
    # Include receipts/reservations for every source revision of the edition.
    # Per-date digest identity remains immutable after first intent.
    metadata = {"snapshot_id": snapshot_id, "ranking_date": ranking_date, "period": _period(now)}
    accepted = next((item for item in old if item.status == "sent"), None)
    uncertain = next((item for item in old if item.status == "pending" and item.attempts > 0
                      and item.last_error_code != "http_429" and item.superseded_by is None), None)
    legacy = accepted or uncertain
    if legacy:
        metadata.update(legacy_event_id=legacy.id, legacy_attempt_id=legacy.attempt_id)
    ledger = _plan(ledger, identity=identity, event_type="edition_digest", message=message, metadata=metadata, now=now)
    item = ledger.latest()[identity]
    if accepted:
        ledger = _transition(ledger, item, state="provider_accepted", now=now, provider=accepted.provider)
    elif uncertain:
        ledger = _transition(ledger, item, state="delivery_unknown", now=now, provider=uncertain.provider,
                             error_code="legacy_outcome_unknown", risk="possible_loss")
        ledger = _alert(ledger, ledger.latest()[identity], now)
    return ledger


def plan_weekly_status(ledger: DeliveryLedger, *, period: str, last_verified_date: str | None,
                       checked_at: str, now: str, status: str = "NO_NEW_EDITION_OBSERVED") -> DeliveryLedger:
    _date(period)
    message = (f"ATP status semanal ({period}): {status}. "
               f"Última classificação verificada: {last_verified_date or 'desconhecida'}. "
               f"Checagem: {checked_at}. Data anterior não é nova publicação.")
    return _plan(ledger, identity=f"status:{period}", event_type="weekly_status", message=message,
                 metadata={"period": period, "last_verified_date": last_verified_date,
                           "checked_at": checked_at, "status": status}, now=now)


@dataclass(frozen=True)
class DeliveryReport:
    accepted: int = 0
    unknown: int = 0
    rejected: int = 0
    retrying: int = 0
    ops_pending: int = 0


def deliver_autonomously(*, path: Path, provider: NotificationProvider | None,
                         checkpoint: Callable[[], None], now: Callable[[], str],
                         ops_alert: Callable[[str, str], bool] | None = None,
                         max_sends: int = 8, max_attempts: int = 4,
                         allow_editions: bool = True) -> DeliveryReport:
    """Caller holds state_lock. Never use the sporting provider for ops alerts.

    Safe rejection (429) retries on later cycles with bounded persisted backoff.
    Checkpoint failure propagates before sending. After a crashed reservation,
    recovery chooses possible loss over duplication without a manual gate.
    Operational sink returns True only after durably persisting the event_id.
    Its receiver deduplicates retries, so ops retry indefinitely with capped
    backoff, including interrupted calls; acceptance is not device delivery.
    """
    if not callable(checkpoint) or max_sends < 1 or max_attempts < 1:
        raise StorageError("invalid_delivery_configuration")
    ledger = load_delivery(path)
    counts = {"accepted": 0, "unknown": 0, "rejected": 0}

    def persist(updated: DeliveryLedger) -> None:
        save_delivery(path, updated)
        checkpoint()

    # Finish interrupted requests before deciding what fresh work to send.
    for item in tuple(ledger.latest().values()):
        if item["state"] == "reserved":
            if item["channel"] == "operational":
                ledger = _transition(ledger, item, state="retry_wait", now=now(),
                                     error_code="interrupted_ops_attempt",
                                     next_attempt_at=_stamp(_time(now()) + timedelta(seconds=60)))
                continue
            ledger = _transition(ledger, item, state="delivery_unknown", now=now(),
                                 error_code="interrupted_attempt", risk="possible_loss")
            if item["channel"] == "sporting":
                ledger = _alert(ledger, ledger.latest()[item["event_id"]], now())
            counts["unknown"] += 1
    # Keep historical intentions; supersede only definitely unattempted/rejected
    # older editions and weekly periods. Never turn old rankings into fresh data.
    latest = ledger.latest()
    newest_date = max((i["metadata"]["ranking_date"] for i in latest.values() if i["event_type"] == "edition_digest"), default=None)
    current_period = _period(now())
    for item in tuple(latest.values()):
        if item["state"] not in {"planned", "retry_wait"} or item["channel"] != "sporting":
            continue
        obsolete = (item["event_type"] == "edition_digest" and item["metadata"]["ranking_date"] < newest_date) or (item["event_type"] == "weekly_status" and item["metadata"]["period"] < current_period)
        if obsolete:
            ledger = _transition(ledger, item, state="suppressed", now=now(), error_code="superseded_backlog")
    persist(ledger)
    sends = {"sporting": 0, "operational": 0}
    # Separate budgets prevent an unavailable channel from starving the other.
    initial = ledger.latest()
    queue = sorted(initial, key=lambda key: (initial[key]["channel"] != "operational", initial[key]["at"], key))
    for identity in queue:
        item = ledger.latest()[identity]
        if item["state"] not in {"planned", "retry_wait"}:
            continue
        if item["event_type"] == "edition_digest" and not allow_editions:
            continue
        if item["state"] == "retry_wait" and _time(item["next_attempt_at"]) > _time(now()):
            continue
        if (item["channel"] == "operational" and ops_alert is None) or (item["channel"] == "sporting" and provider is None):
            continue
        if sends[item["channel"]] >= max_sends:
            continue
        if item["channel"] == "sporting" and item["attempts"] >= max_attempts:
            ledger = _transition(ledger, item, state="rejected", now=now(), error_code="retry_exhausted")
            if item["channel"] == "sporting":
                ledger = _alert(ledger, ledger.latest()[identity], now())
            persist(ledger)
            counts["rejected"] += 1
            continue
        ledger = _transition(ledger, item, state="reserved", now=now(), attempts=item["attempts"] + 1,
                             attempt_id=uuid4().hex, provider="independent-ops" if item["channel"] == "operational" else provider.name,
                             error_code=None)
        persist(ledger)
        sends[item["channel"]] += 1
        reserved = ledger.latest()[identity]
        http_status = None
        try:
            if item["channel"] == "operational":
                if ops_alert(identity, item["message"]) is not True:
                    raise DeliveryError("ops_sink_unavailable", 1, retryable=True)
            else:
                receipt = provider.send(event_id=identity, message=item["message"])
                if receipt.provider != provider.name or receipt.delivery_status != "provider_accepted" or receipt.delivered_to_device:
                    raise DeliveryError("provider_response_ambiguous", 1)
                http_status = receipt.http_status
            state, code, risk, next_at = "provider_accepted", None, None, None
        except Exception as exc:
            # Persist only allowlisted stable codes; adapter text may contain secrets.
            code = exc.code if isinstance(exc, DeliveryError) and (exc.code in _SAFE_ERRORS or re.fullmatch(r"http_[1-5][0-9]{2}", exc.code)) else "provider_error"
            if re.fullmatch(r"http_[1-5][0-9]{2}", code):
                http_status = int(code[5:])
            if item["channel"] == "operational":
                # Receiver durably deduplicates this event_id across requests.
                code = "ops_sink_unavailable"
            safe_retry = item["channel"] == "operational" or (isinstance(exc, DeliveryError) and exc.retryable and code == "http_429")
            if safe_retry and (item["channel"] == "operational" or reserved["attempts"] < max_attempts):
                state, risk = "retry_wait", None
                next_at = _stamp(_time(now()) + timedelta(seconds=min(3600, 60 * 2 ** min(6, reserved["attempts"] - 1))))
            elif safe_retry or code == "invalid_message" or (re.fullmatch(r"http_4[0-9]{2}", code) and code != "http_408"):
                state, risk, next_at = "rejected", None, None
            else:
                state, risk, next_at = "delivery_unknown", "possible_loss", None
        ledger = _transition(ledger, reserved, state=state, now=now(), error_code=code,
                             risk=risk, next_attempt_at=next_at, http_status=http_status)
        if state in {"delivery_unknown", "rejected"} and item["channel"] == "sporting":
            ledger = _alert(ledger, ledger.latest()[identity], now())
        persist(ledger)
        queue.extend(key for key, value in ledger.latest().items()
                     if value["channel"] == "operational" and key not in queue)
        if state == "provider_accepted":
            counts["accepted"] += 1
        elif state == "delivery_unknown":
            counts["unknown"] += 1
        elif state == "rejected":
            counts["rejected"] += 1
    remaining = tuple(ledger.latest().values())
    return DeliveryReport(**counts, retrying=sum(i["state"] == "retry_wait" for i in remaining),
                          ops_pending=sum(i["channel"] == "operational" and i["state"] in {"planned", "retry_wait"} for i in remaining))
