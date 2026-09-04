"""Validated local enrichment of ranking observations with career highs.

The source is deliberately not trusted to supply career-high data.  A
versioned, manually verified baseline and the local snapshot history are the
only inputs used to calculate it.  Invalid or incomplete baseline data stops
collection before a caller can persist a snapshot.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .domain import (
    PLAYER_ATP_ID,
    PLAYER_NAME,
    DisciplineRanking,
    RankingObservation,
    RankingSnapshot,
    normalize_player_name,
)


DEFAULT_BASELINE_PATH = Path(__file__).resolve().parents[2] / "data" / "ranking_career_high_baseline.json"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_REFERENCE_PLACEHOLDERS = frozenset(
    {
        "manual-verification-reference",
        "unverified",
    }
)


class CareerHighBaselineError(ValueError):
    """Safe, stable error for a baseline that cannot be used."""

    code = "career_high_baseline_invalid"

    def __init__(self) -> None:
        super().__init__(self.code)


# A short alias keeps the public failure type convenient for callers while
# retaining a name that makes the failing input explicit.
CareerHighError = CareerHighBaselineError


@dataclass(frozen=True, kw_only=True)
class BaselineDiscipline:
    rank: int
    ranking_date: str
    reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank <= 0:
            _invalid()
        _date_value(self.ranking_date)
        _reference_value(self.reference)


@dataclass(frozen=True, kw_only=True)
class CareerHighBaseline:
    verified_at: str
    singles: BaselineDiscipline
    doubles: BaselineDiscipline

    def __post_init__(self) -> None:
        verified_at = _timestamp_value(self.verified_at)
        if not isinstance(self.singles, BaselineDiscipline) or not isinstance(
            self.doubles, BaselineDiscipline
        ):
            _invalid()
        if (
            self.singles.ranking_date > verified_at[:10]
            or self.doubles.ranking_date > verified_at[:10]
        ):
            _invalid()


def _invalid() -> None:
    raise CareerHighBaselineError()


def _date_value(value: Any) -> str:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        _invalid()
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _invalid()
    if parsed.isoformat() != value:
        _invalid()
    return value


def _timestamp_value(value: Any) -> str:
    if not isinstance(value, str) or not _TIMESTAMP_RE.fullmatch(value):
        _invalid()
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _invalid()
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _invalid()
    return value


def _reference_value(value: Any) -> str:
    if not isinstance(value, str):
        _invalid()
    normalized = " ".join(value.casefold().split())
    if (
        not normalized
        or normalized in _REFERENCE_PLACEHOLDERS
        or normalized.startswith("replace with ")
    ):
        _invalid()
    return value


def _discipline(value: Any, *, verified_at: str) -> BaselineDiscipline:
    if not isinstance(value, Mapping) or set(value) != {"rank", "ranking_date", "reference"}:
        _invalid()
    rank = value["rank"]
    if not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0:
        # In particular, the documented rank=0 template is never activatable.
        _invalid()
    ranking_date = _date_value(value["ranking_date"])
    reference = _reference_value(value["reference"])
    if ranking_date > verified_at[:10]:
        _invalid()
    return BaselineDiscipline(rank=rank, ranking_date=ranking_date, reference=reference)


def parse_baseline(value: Any) -> CareerHighBaseline:
    """Validate a decoded baseline document without exposing its contents."""

    required = {"schema_version", "player", "verified_at", "disciplines"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema_version") != 1:
        _invalid()
    player = value["player"]
    disciplines = value["disciplines"]
    if (
        not isinstance(player, Mapping)
        or set(player) != {"atp_id", "name"}
        or player.get("atp_id") != PLAYER_ATP_ID
        or normalize_player_name(player.get("name")) != normalize_player_name(PLAYER_NAME)
        or not isinstance(disciplines, Mapping)
        or set(disciplines) != {"singles", "doubles"}
    ):
        _invalid()
    verified_at = _timestamp_value(value["verified_at"])
    return CareerHighBaseline(
        verified_at=verified_at,
        singles=_discipline(disciplines["singles"], verified_at=verified_at),
        doubles=_discipline(disciplines["doubles"], verified_at=verified_at),
    )


def load_baseline(path: str | Path = DEFAULT_BASELINE_PATH) -> CareerHighBaseline:
    """Load the baseline or fail closed with a sanitized error code."""

    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return parse_baseline(json.load(handle))
    except CareerHighBaselineError:
        raise
    except (OSError, TypeError, json.JSONDecodeError, ValueError):
        raise CareerHighBaselineError() from None


load_career_high_baseline = load_baseline


@dataclass(frozen=True, kw_only=True)
class _High:
    rank: int
    ranking_date: str


def _history_highs(
    history: Iterable[RankingSnapshot],
    *,
    discipline: str,
    observation_date: str,
) -> tuple[_High, ...]:
    values: list[_High] = []
    for snapshot in history:
        if not isinstance(snapshot, RankingSnapshot) or snapshot.ranking_date > observation_date:
            _invalid()
        ranking = getattr(snapshot, discipline)
        if not isinstance(ranking, DisciplineRanking):
            _invalid()
        if (ranking.career_high_rank is None) != (ranking.career_high_date is None):
            _invalid()
        if ranking.rank is not None:
            values.append(_High(rank=ranking.rank, ranking_date=snapshot.ranking_date))
        if ranking.career_high_rank is not None:
            if ranking.career_high_date > snapshot.ranking_date:
                _invalid()
            # Legacy career-high fields are derived data, not independent
            # observations. Validate them, but never promote them into the new
            # manually anchored calculation.
    return tuple(values)


def _enriched_discipline(
    ranking: DisciplineRanking,
    *,
    baseline: BaselineDiscipline,
    history: Iterable[RankingSnapshot],
    observation_date: str,
    discipline: str,
) -> DisciplineRanking:
    candidates = [_High(rank=baseline.rank, ranking_date=baseline.ranking_date)]
    candidates.extend(_history_highs(history, discipline=discipline, observation_date=observation_date))
    if ranking.rank is not None:
        candidates.append(_High(rank=ranking.rank, ranking_date=observation_date))
    high = min(candidates, key=lambda item: (item.rank, item.ranking_date))
    return replace(ranking, career_high_rank=high.rank, career_high_date=high.ranking_date)


def enrich_career_high(
    observation: RankingObservation,
    *,
    baseline: CareerHighBaseline,
    history: Iterable[RankingSnapshot] = (),
) -> RankingObservation:
    """Return an observation whose career highs come from local evidence.

    The current source-provided career-high fields are intentionally replaced.
    ``history`` must contain only snapshots at or before the observation date;
    accepting a later snapshot would make the result depend on future data.
    """

    if not isinstance(observation, RankingObservation) or not isinstance(baseline, CareerHighBaseline):
        _invalid()
    if baseline.singles.ranking_date > observation.ranking_date or baseline.doubles.ranking_date > observation.ranking_date:
        _invalid()
    snapshots = tuple(history)
    return replace(
        observation,
        singles=_enriched_discipline(
            observation.singles,
            baseline=baseline.singles,
            history=snapshots,
            observation_date=observation.ranking_date,
            discipline="singles",
        ),
        doubles=_enriched_discipline(
            observation.doubles,
            baseline=baseline.doubles,
            history=snapshots,
            observation_date=observation.ranking_date,
            discipline="doubles",
        ),
    )


def enrich_with_baseline(
    observation: RankingObservation,
    *,
    history: Iterable[RankingSnapshot] = (),
    baseline_path: str | Path = DEFAULT_BASELINE_PATH,
) -> RankingObservation:
    """Load the on-disk baseline and enrich an observation in one call."""

    return enrich_career_high(observation, baseline=load_baseline(baseline_path), history=history)
