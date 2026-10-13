"""Safe Actions summaries for scheduler timing and publication freshness."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from .freshness import CalendarError, FreshnessAssessment, _aware


@dataclass(frozen=True)
class ScheduleTiming:
    event: str
    expected_at: str | None
    started_at: str
    delay_minutes: float | None
    delayed_over_60_minutes: bool


def _iso(instant: datetime) -> str:
    return instant.isoformat().replace("+00:00", "Z")


def schedule_timing(*, event: str, created_at: datetime, started_at: datetime) -> ScheduleTiming:
    """Infer Tue–Fri 12:00 UTC / Thu 15:05 UTC slots from run creation.

    GitHub's schedule payload has a cron string, but no nominal occurrence
    timestamp. The last eligible slot at run creation is the stated estimate;
    run_started_at comes from the Actions API. Manual runs have no delay SLA.
    """
    created, started = _aware(created_at), _aware(started_at)
    if started < created:
        raise CalendarError()
    if event != "schedule":
        return ScheduleTiming(event, None, _iso(started), None, False)
    candidates = []
    for offset in range(8):
        day = created - timedelta(days=offset)
        nominal = day.replace(hour=12, minute=0, second=0, microsecond=0)
        if day.weekday() in {1, 2, 3, 4} and nominal <= created:
            candidates.append(nominal)
        after_cutoff = day.replace(hour=15, minute=5, second=0, microsecond=0)
        if day.weekday() == 3 and after_cutoff <= created:
            candidates.append(after_cutoff)
    expected = max(candidates)
    delay = (started - expected).total_seconds() / 60
    return ScheduleTiming(event, _iso(expected), _iso(started), round(delay, 2), delay > 60)


def append_summary(text: str, *, path: Path | None = None) -> None:
    target = path or (Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None)
    if target is not None:
        with target.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")


def emit_schedule_summary(report: ScheduleTiming, *, source_age_days: int | None, path: Path | None = None) -> None:
    print("schedule_telemetry=" + json.dumps(asdict(report), sort_keys=True))
    warning = "DELAY >60 minutes" if report.delayed_over_60_minutes else "Within timing threshold" if report.event == "schedule" else "Manual run — no scheduled delay"
    append_summary(
        "### ATP ranking — schedule\n\n"
        f"- Expected slot (UTC, inferred from run creation): {report.expected_at or 'manual'}\n"
        f"- Actual workflow start (UTC, Actions API): {report.started_at}\n"
        f"- Delay: {report.delay_minutes if report.delay_minutes is not None else 'n/a'} minutes; {warning}\n"
        f"- Last persisted source age: {source_age_days if source_age_days is not None else 'unknown'} days\n\n"
        "GitHub cron does not guarantee punctual execution. The schedule payload has no nominal occurrence timestamp; delay is measured against the preceding eligible slot.\n",
        path=path,
    )


def safe_source_telemetry(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    # Values from ItfRankingSource are already redacted at acquisition. Keep
    # only its documented diagnostic contract, never arbitrary extra fields.
    keys = {"source", "atp_id", "itf_player_id", "started_at", "completed_at", "navigation_status", "navigation_error", "final_url", "page_title", "page_kind", "dom_identity", "cache_headers", "source_ranking_date", "error_code"}
    result = {key: value[key] for key in keys if key in value}
    for discipline in ("singles", "doubles"):
        entry = value.get(discipline)
        if isinstance(entry, Mapping):
            result[discipline] = {key: entry[key] for key in ("http_status", "retrieved_at", "ranking_date", "cache_headers", "json_object", "rank") if key in entry}
    return result


def emit_collection_summary(
    assessment: FreshnessAssessment | None,
    *,
    source_telemetry: Any = None,
    error_code: str | None = None,
    path: Path | None = None,
) -> None:
    telemetry = safe_source_telemetry(source_telemetry)
    if telemetry:
        print("source_telemetry=" + json.dumps(telemetry, sort_keys=True))
    rows = ["### ATP ranking — publication", ""]
    if assessment:
        rows.extend((
            f"- Freshness: **{assessment.state.value}**",
            f"- Expected edition: {assessment.expected_date}",
            f"- Observed edition: {assessment.actual_date or 'unknown'}",
            f"- Last valid persisted edition: {assessment.last_valid_date or 'none'}",
            f"- Publication cutoff (UTC): {assessment.cutoff}",
            f"- Source age: {assessment.source_age_days if assessment.source_age_days is not None else 'unknown'} days",
            f"- Calendar version: {assessment.calendar_version}",
        ))
        if assessment.state.value == "PENDING_PUBLICATION":
            rows.append("- Awaiting publication within its grace period; no publication SLA violation.")
    elif error_code:
        rows.append("- Freshness: **SOURCE_ERROR** (no usable observation)")
    if error_code:
        rows.append(f"- Sanitized error: {error_code}")
    if telemetry:
        rows.extend(("", "```json", json.dumps(telemetry, sort_keys=True, indent=2), "```"))
    append_summary("\n".join(rows) + "\n", path=path)
