"""Isolated recovery from the qualified source; never creates alert intentions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .career_high import DEFAULT_BASELINE_PATH, enrich_with_baseline
from .domain import (
    DisciplineRanking, DomainValidationError, RankingObservation, RankingsData,
    build_snapshot, normalize_player_name, observation_from_snapshot, snapshot_sort_key,
)
from .source import RawRankingObservation, RankingSource, RankingSourceError
from .storage import load_alert_state, load_rankings, save_rankings


@dataclass(frozen=True)
class BackfillOutcome:
    status: str
    rankings: RankingsData
    snapshot_id: str
    ranking_date: str


def backfill(*, source: RankingSource, as_of: str, rankings_path: Path, state_path: Path,
             captured_at: str, apply: bool = False,
             baseline_path: Path = DEFAULT_BASELINE_PATH) -> BackfillOutcome:
    """Recover only the requested source-confirmed edition, without delivery.

    The qualified ITF adapter performs identity, HTTP, discipline and edition
    validation. This deliberately bypasses *current* freshness for a historical
    edition, while retaining every other validation and rejecting revisions.
    """
    rankings = load_rankings(rankings_path)
    load_alert_state(state_path, rankings)
    if getattr(source, "name", None) != "itf":
        raise DomainValidationError("unqualified_backfill_source")
    raw = source.fetch()
    if not isinstance(raw, RawRankingObservation) or raw.source != "itf":
        raise RankingSourceError("ranking_source_incomplete")
    if raw.ranking_date != as_of:
        raise DomainValidationError("backfill_edition_unverified")
    try:
        captured_date = datetime.fromisoformat(captured_at.replace("Z", "+00:00")).date().isoformat()
    except (ValueError, AttributeError):
        raise DomainValidationError("invalid_captured_at") from None
    if as_of > captured_date:
        raise DomainValidationError("backfill_edition_future")
    if raw.atp_id != "B0UF" or normalize_player_name(raw.name) != normalize_player_name("Luka Bojicic Ono"):
        raise RankingSourceError("ranking_source_identity_mismatch")
    observation = RankingObservation(
        atp_id=raw.atp_id, name=raw.name, source=raw.source, ranking_date=raw.ranking_date,
        singles=DisciplineRanking(rank=raw.singles.rank, points=raw.singles.points),
        doubles=DisciplineRanking(rank=raw.doubles.rank, points=raw.doubles.points),
    )
    history = tuple(snapshot for snapshot in rankings.snapshots if snapshot.ranking_date < as_of)
    observation = enrich_with_baseline(observation, history=history, baseline_path=baseline_path)
    candidate = build_snapshot(observation, captured_at)
    existing = tuple(snapshot for snapshot in rankings.snapshots if snapshot.ranking_date == as_of)
    if existing:
        latest = existing[-1]
        if latest.singles != candidate.singles or latest.doubles != candidate.doubles:
            raise DomainValidationError("backfill_revision_requires_review")
        return BackfillOutcome("unchanged", rankings, latest.id, as_of)
    updated = RankingsData(
        schema_version=rankings.schema_version, atp_id=rankings.atp_id, player_name=rankings.player_name,
        snapshots=tuple(sorted(rankings.snapshots + (candidate,), key=snapshot_sort_key)),
    )
    for later in rankings.snapshots:
        if later.ranking_date <= as_of:
            continue
        prior = tuple(snapshot for snapshot in updated.snapshots if snapshot.ranking_date < later.ranking_date)
        recalculated = enrich_with_baseline(observation_from_snapshot(later), history=prior, baseline_path=baseline_path)
        if recalculated.singles != later.singles or recalculated.doubles != later.doubles:
            # Do not rewrite hashed historical facts or receipts to repair a
            # newly discovered career high. Require explicit reconciliation.
            raise DomainValidationError("backfill_career_high_requires_review")
    if apply:
        save_rankings(rankings_path, updated)
    return BackfillOutcome("created" if apply else "would_create", updated, candidate.id, as_of)
