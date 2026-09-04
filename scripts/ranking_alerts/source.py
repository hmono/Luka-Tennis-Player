"""Neutral boundary for acquiring ATP ranking observations.

This module intentionally contains no provider URL, credential handling, or
domain/career-high rules.  It is the small contract a qualified provider will
implement after the source-qualification spike has received an explicit go.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


RANKING_SOURCE_ERROR_CODES = frozenset(
    {
        "ranking_source_blocked",
        "ranking_source_authentication",
        "ranking_source_rate_limited",
        "ranking_source_timeout",
        "ranking_source_schema_changed",
        "ranking_source_identity_mismatch",
        "ranking_source_incomplete",
        "ranking_source_coverage_truncated",
    }
)


class RankingSourceError(RuntimeError):
    """A safe-to-log source failure represented exclusively by a stable code."""

    def __init__(self, code: str) -> None:
        if code not in RANKING_SOURCE_ERROR_CODES:
            raise ValueError("invalid_ranking_source_error_code")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, kw_only=True)
class RawDisciplineRanking:
    """Ranking values supplied by a provider before domain validation."""

    status: Literal["ranked", "unranked"]
    rank: int | None
    points: int

    def __post_init__(self) -> None:
        if self.status not in {"ranked", "unranked"}:
            raise ValueError("invalid_ranking_status")
        if isinstance(self.points, bool) or not isinstance(self.points, int) or self.points < 0:
            raise ValueError("invalid_ranking_points")
        if self.status == "ranked":
            if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank <= 0:
                raise ValueError("invalid_ranked_rank")
        elif self.rank is not None:
            raise ValueError("invalid_unranked_rank")


@dataclass(frozen=True, kw_only=True)
class RawRankingObservation:
    """Complete provider-supplied observation, without derived career highs."""

    source: str
    atp_id: str
    name: str
    ranking_date: str
    singles: RawDisciplineRanking
    doubles: RawDisciplineRanking


class RankingSource(Protocol):
    """Explicitly selected provider of one complete raw ranking observation."""

    name: str

    def fetch(self) -> RawRankingObservation: ...
