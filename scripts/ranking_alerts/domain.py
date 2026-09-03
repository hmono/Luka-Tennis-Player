"""Typed domain model for ATP rankings, changes, and the durable outbox."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

PLAYER_ATP_ID = "B0UF"
PLAYER_NAME = "Luka Bojicic Ono"
SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class DomainValidationError(ValueError):
    """A validation error whose printable form is safe for logs/state."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _iso_date(value: str | None, *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise DomainValidationError("invalid_ranking_date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise DomainValidationError("invalid_ranking_date") from exc
    if parsed.isoformat() != value:
        raise DomainValidationError("invalid_ranking_date")
    return value


def _utc_timestamp(value: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DomainValidationError("invalid_captured_at")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise DomainValidationError("invalid_captured_at") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise DomainValidationError("invalid_captured_at")
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_player_name(value: str) -> str:
    if not isinstance(value, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_name = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(ascii_name.casefold().split())


@dataclass(frozen=True, kw_only=True)
class DisciplineRanking:
    rank: int | None
    points: int
    career_high_rank: int | None = None
    career_high_date: str | None = None

    def __post_init__(self) -> None:
        if self.rank is not None and (not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank <= 0):
            raise DomainValidationError("invalid_rank")
        if not isinstance(self.points, int) or isinstance(self.points, bool) or self.points < 0:
            raise DomainValidationError("invalid_points")
        if self.career_high_rank is not None and (
            not isinstance(self.career_high_rank, int)
            or isinstance(self.career_high_rank, bool)
            or self.career_high_rank <= 0
        ):
            raise DomainValidationError("invalid_career_high")
        if self.rank is not None and self.career_high_rank is not None and self.career_high_rank > self.rank:
            raise DomainValidationError("invalid_career_high")
        _iso_date(self.career_high_date, required=False)


@dataclass(frozen=True, kw_only=True)
class RankingObservation:
    atp_id: str
    name: str
    ranking_date: str
    singles: DisciplineRanking
    doubles: DisciplineRanking
    source: str = "atptour"

    def __post_init__(self) -> None:
        if self.atp_id != PLAYER_ATP_ID or normalize_player_name(self.name) != normalize_player_name(PLAYER_NAME):
            raise DomainValidationError("atp_identity_mismatch")
        _iso_date(self.ranking_date)
        if self.source != "atptour":
            raise DomainValidationError("invalid_source")
        if not isinstance(self.singles, DisciplineRanking) or not isinstance(self.doubles, DisciplineRanking):
            raise DomainValidationError("atp_incomplete_observation")


@dataclass(frozen=True, kw_only=True)
class RankingSnapshot:
    id: str
    ranking_date: str
    captured_at: str
    source: str
    singles: DisciplineRanking
    doubles: DisciplineRanking
    source_revision_of: str | None = None

    def __post_init__(self) -> None:
        if not _SHA256_RE.fullmatch(self.id):
            raise DomainValidationError("invalid_snapshot_id")
        _iso_date(self.ranking_date)
        _utc_timestamp(self.captured_at)
        if self.source != "atptour":
            raise DomainValidationError("invalid_source")
        if self.source_revision_of is not None and not _SHA256_RE.fullmatch(self.source_revision_of):
            raise DomainValidationError("invalid_revision_reference")


@dataclass(frozen=True, kw_only=True)
class DisciplineDelta:
    rank_delta: int | None = None
    points_delta: int | None = None
    entered_ranking: bool = False
    left_ranking: bool = False
    new_career_high: int | None = None

    @property
    def has_changes(self) -> bool:
        return any(
            (
                self.rank_delta not in (None, 0),
                self.points_delta not in (None, 0),
                self.entered_ranking,
                self.left_ranking,
                self.new_career_high is not None,
            )
        )


@dataclass(frozen=True, kw_only=True)
class RankingDelta:
    singles: DisciplineDelta
    doubles: DisciplineDelta

    @property
    def has_changes(self) -> bool:
        return self.singles.has_changes or self.doubles.has_changes


@dataclass(frozen=True, kw_only=True)
class RankingsData:
    schema_version: int = SCHEMA_VERSION
    atp_id: str = PLAYER_ATP_ID
    player_name: str = PLAYER_NAME
    snapshots: tuple[RankingSnapshot, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise DomainValidationError("unsupported_schema_version")
        if self.atp_id != PLAYER_ATP_ID or normalize_player_name(self.player_name) != normalize_player_name(PLAYER_NAME):
            raise DomainValidationError("atp_identity_mismatch")
        ordered = tuple(sorted(self.snapshots, key=snapshot_sort_key))
        if ordered != self.snapshots or len({item.id for item in self.snapshots}) != len(self.snapshots):
            raise DomainValidationError("invalid_snapshot_order")
        for snapshot in self.snapshots:
            expected = snapshot_id(observation_from_snapshot(snapshot))
            if snapshot.id != expected:
                raise DomainValidationError("invalid_snapshot_id")
            if snapshot.source_revision_of is not None and snapshot.source_revision_of not in {
                previous.id for previous in self.snapshots if previous.ranking_date == snapshot.ranking_date
            }:
                raise DomainValidationError("invalid_revision_reference")


@dataclass(frozen=True, kw_only=True)
class OutboxItem:
    id: str
    snapshot_id: str
    event_type: str
    status: str = "pending"
    attempts: int = 0
    created_at: str
    sent_at: str | None = None
    provider: str = "callmebot"
    last_error_code: str | None = None

    def __post_init__(self) -> None:
        if not _SHA256_RE.fullmatch(self.id) or not _SHA256_RE.fullmatch(self.snapshot_id):
            raise DomainValidationError("invalid_outbox_id")
        if self.id != event_id(self.snapshot_id, self.event_type):
            raise DomainValidationError("invalid_outbox_id")
        if self.event_type not in {"ranking_change", "ranking_correction"}:
            raise DomainValidationError("invalid_event_type")
        if self.status not in {"pending", "sent"}:
            raise DomainValidationError("invalid_outbox_status")
        if not isinstance(self.attempts, int) or isinstance(self.attempts, bool) or self.attempts < 0:
            raise DomainValidationError("invalid_attempts")
        _utc_timestamp(self.created_at)
        if self.sent_at is not None:
            _utc_timestamp(self.sent_at)
        if (self.status == "sent") != (self.sent_at is not None):
            raise DomainValidationError("invalid_sent_at")
        if self.provider != "callmebot":
            raise DomainValidationError("invalid_provider")
        if self.last_error_code is not None and not re.fullmatch(r"[a-z0-9_]+", self.last_error_code):
            raise DomainValidationError("invalid_error_code")


@dataclass(frozen=True, kw_only=True)
class RankingAlertState:
    schema_version: int = SCHEMA_VERSION
    outbox: tuple[OutboxItem, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise DomainValidationError("unsupported_schema_version")
        if len({item.id for item in self.outbox}) != len(self.outbox):
            raise DomainValidationError("duplicate_outbox_id")


def _discipline_dict(value: DisciplineRanking) -> dict[str, Any]:
    return {
        "rank": value.rank,
        "points": value.points,
        "career_high_rank": value.career_high_rank,
        "career_high_date": value.career_high_date,
    }


def _canonical_observation(observation: RankingObservation) -> dict[str, Any]:
    return {
        "atp_id": observation.atp_id,
        "ranking_date": observation.ranking_date,
        "source": observation.source,
        "singles": _discipline_dict(observation.singles),
        "doubles": _discipline_dict(observation.doubles),
    }


def _stable_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def snapshot_id(observation: RankingObservation) -> str:
    return _stable_hash(_canonical_observation(observation))


def event_id(snapshot_id_value: str, event_type: str) -> str:
    return _stable_hash({"event_type": event_type, "snapshot_id": snapshot_id_value})


def build_snapshot(
    observation: RankingObservation,
    captured_at: str,
    source_revision_of: str | None = None,
) -> RankingSnapshot:
    return RankingSnapshot(
        id=snapshot_id(observation),
        ranking_date=observation.ranking_date,
        captured_at=captured_at,
        source=observation.source,
        singles=observation.singles,
        doubles=observation.doubles,
        source_revision_of=source_revision_of,
    )


def observation_from_snapshot(snapshot: RankingSnapshot) -> RankingObservation:
    return RankingObservation(
        atp_id=PLAYER_ATP_ID,
        name=PLAYER_NAME,
        ranking_date=snapshot.ranking_date,
        source=snapshot.source,
        singles=snapshot.singles,
        doubles=snapshot.doubles,
    )


def snapshot_sort_key(snapshot: RankingSnapshot) -> tuple[str, str, str]:
    return snapshot.ranking_date, snapshot.captured_at, snapshot.id


def _known_high(history: Iterable[RankingSnapshot], discipline: str) -> int | None:
    values: list[int] = []
    for snapshot in history:
        ranking = getattr(snapshot, discipline)
        if ranking.rank is not None:
            values.append(ranking.rank)
        if ranking.career_high_rank is not None:
            values.append(ranking.career_high_rank)
    return min(values) if values else None


def _discipline_delta(
    previous: DisciplineRanking,
    current: DisciplineRanking,
    known_high: int | None,
) -> DisciplineDelta:
    entered = previous.rank is None and current.rank is not None
    left = previous.rank is not None and current.rank is None
    rank_delta = previous.rank - current.rank if previous.rank is not None and current.rank is not None else None
    points_delta = current.points - previous.points
    new_high = current.rank if current.rank is not None and (known_high is None or current.rank < known_high) else None
    return DisciplineDelta(
        rank_delta=rank_delta,
        points_delta=points_delta,
        entered_ranking=entered,
        left_ranking=left,
        new_career_high=new_high,
    )


def compare_snapshots(
    previous: RankingSnapshot,
    current: RankingSnapshot,
    history: Iterable[RankingSnapshot] = (),
) -> RankingDelta:
    prior = tuple(history)
    if all(item.id != previous.id for item in prior):
        prior = prior + (previous,)
    return RankingDelta(
        singles=_discipline_delta(previous.singles, current.singles, _known_high(prior, "singles")),
        doubles=_discipline_delta(previous.doubles, current.doubles, _known_high(prior, "doubles")),
    )


def _rank(value: int | None) -> str:
    return "não classificado" if value is None else f"#{value:,}".replace(",", ".")


def _signed(value: int) -> str:
    return "0" if value == 0 else f"{value:+d}"


def _discipline_line(label: str, ranking: DisciplineRanking, delta: DisciplineDelta) -> str:
    if delta.entered_ranking:
        rank_part = f"{_rank(ranking.rank)} (entrou no ranking)"
    elif delta.left_ranking:
        rank_part = "não classificado (saiu do ranking)"
    elif delta.rank_delta is not None:
        rank_part = f"{_rank(ranking.rank)} ({_signed(delta.rank_delta)})"
    else:
        rank_part = _rank(ranking.rank)
    points = f"{ranking.points:,}".replace(",", ".") + " pts"
    if delta.points_delta is not None:
        points += f" ({_signed(delta.points_delta)})"
    return f"{label}: {rank_part} | {points}"


def format_message(current: RankingSnapshot, delta: RankingDelta) -> str:
    lines = [
        f"ATP Ranking — {current.ranking_date}",
        _discipline_line("Singles", current.singles, delta.singles),
        _discipline_line("Doubles", current.doubles, delta.doubles),
    ]
    highs: list[str] = []
    if delta.singles.new_career_high is not None:
        highs.append(f"Singles {_rank(delta.singles.new_career_high)}")
    if delta.doubles.new_career_high is not None:
        highs.append(f"Doubles {_rank(delta.doubles.new_career_high)}")
    if highs:
        lines.append("Novo career high: " + ", ".join(highs))
    return "\n".join(lines)


def discipline_from_dict(value: Any) -> DisciplineRanking:
    if not isinstance(value, Mapping):
        raise DomainValidationError("atp_incomplete_observation")
    required = {"rank", "points", "career_high_rank", "career_high_date"}
    if set(value) != required:
        raise DomainValidationError("atp_schema_changed")
    return DisciplineRanking(
        rank=value["rank"],
        points=value["points"],
        career_high_rank=value["career_high_rank"],
        career_high_date=value["career_high_date"],
    )


def snapshot_to_dict(snapshot: RankingSnapshot) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": snapshot.id,
        "ranking_date": snapshot.ranking_date,
        "captured_at": snapshot.captured_at,
        "source": snapshot.source,
        "singles": _discipline_dict(snapshot.singles),
        "doubles": _discipline_dict(snapshot.doubles),
    }
    if snapshot.source_revision_of is not None:
        result["source_revision_of"] = snapshot.source_revision_of
    return result


def snapshot_from_dict(value: Any) -> RankingSnapshot:
    if not isinstance(value, Mapping):
        raise DomainValidationError("invalid_snapshot")
    allowed = {"id", "ranking_date", "captured_at", "source", "singles", "doubles", "source_revision_of"}
    if not {"id", "ranking_date", "captured_at", "source", "singles", "doubles"}.issubset(value) or set(value) - allowed:
        raise DomainValidationError("invalid_snapshot")
    return RankingSnapshot(
        id=value["id"],
        ranking_date=value["ranking_date"],
        captured_at=value["captured_at"],
        source=value["source"],
        singles=discipline_from_dict(value["singles"]),
        doubles=discipline_from_dict(value["doubles"]),
        source_revision_of=value.get("source_revision_of"),
    )


def rankings_to_dict(data: RankingsData) -> dict[str, Any]:
    return {
        "schema_version": data.schema_version,
        "player": {"atp_id": data.atp_id, "name": data.player_name},
        "snapshots": [snapshot_to_dict(item) for item in data.snapshots],
    }


def rankings_from_dict(value: Any) -> RankingsData:
    if not isinstance(value, Mapping) or set(value) != {"schema_version", "player", "snapshots"}:
        raise DomainValidationError("invalid_rankings_document")
    player = value["player"]
    if not isinstance(player, Mapping) or set(player) != {"atp_id", "name"} or not isinstance(value["snapshots"], list):
        raise DomainValidationError("invalid_rankings_document")
    return RankingsData(
        schema_version=value["schema_version"],
        atp_id=player["atp_id"],
        player_name=player["name"],
        snapshots=tuple(snapshot_from_dict(item) for item in value["snapshots"]),
    )


def outbox_to_dict(item: OutboxItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "snapshot_id": item.snapshot_id,
        "event_type": item.event_type,
        "status": item.status,
        "attempts": item.attempts,
        "created_at": item.created_at,
        "sent_at": item.sent_at,
        "provider": item.provider,
        "last_error_code": item.last_error_code,
    }


def outbox_from_dict(value: Any) -> OutboxItem:
    required = {
        "id", "snapshot_id", "event_type", "status", "attempts", "created_at",
        "sent_at", "provider", "last_error_code",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise DomainValidationError("invalid_outbox_item")
    return OutboxItem(**{key: value[key] for key in required})


def state_to_dict(state: RankingAlertState) -> dict[str, Any]:
    return {"schema_version": state.schema_version, "outbox": [outbox_to_dict(item) for item in state.outbox]}


def state_from_dict(value: Any) -> RankingAlertState:
    if not isinstance(value, Mapping) or set(value) != {"schema_version", "outbox"} or not isinstance(value["outbox"], list):
        raise DomainValidationError("invalid_alert_state")
    return RankingAlertState(
        schema_version=value["schema_version"],
        outbox=tuple(outbox_from_dict(item) for item in value["outbox"]),
    )
