"""Edition expectations and SLA, without inventing sporting observations.

The versioned calendar describes expected publication dates, not observed
editions. Only a verified source response may create a sporting snapshot.
Official no-edition or moved-edition notices are explicit, referenced overrides.
The calendar expires instead of silently assuming next year's rules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo


DEFAULT_CALENDAR_PATH = Path(__file__).resolve().parents[2] / "config" / "atp_publication_calendar.json"


class CalendarError(ValueError):
    code = "ranking_calendar_invalid"

    def __init__(self) -> None:
        super().__init__(self.code)


class FreshnessState(str, Enum):
    FRESH = "FRESH"
    PENDING_PUBLICATION = "PENDING_PUBLICATION"
    STALE = "STALE"
    SOURCE_ERROR = "SOURCE_ERROR"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _date(value: Any) -> date:
    if not isinstance(value, str):
        raise CalendarError()
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise CalendarError() from None
    if result.isoformat() != value:
        raise CalendarError()
    return result


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CalendarError()
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class EditionCalendar:
    version: str
    valid_from: date
    valid_until: date
    publication_weekday: int
    cutoff_zone: ZoneInfo
    cutoff_days: int
    cutoff_time: time
    exceptions: tuple[tuple[date, date | None], ...] = ()

    def editions(self, through: date) -> tuple[date, ...]:
        if not self.valid_from <= through <= self.valid_until:
            raise CalendarError()
        overrides = dict(self.exceptions)
        cursor = self.valid_from + timedelta(days=(self.publication_weekday - self.valid_from.weekday()) % 7)
        values: set[date] = set()
        while cursor <= self.valid_until:
            edition = overrides.get(cursor, cursor)
            if edition is not None and edition <= through:
                values.add(edition)
            cursor += timedelta(days=7)
        return tuple(sorted(values))

    def cutoff_for(self, edition: date) -> datetime:
        return datetime.combine(edition + timedelta(days=self.cutoff_days), self.cutoff_time, self.cutoff_zone).astimezone(timezone.utc)


def calendar_from_dict(value: Any) -> EditionCalendar:
    try:
        if not isinstance(value, Mapping) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
            raise CalendarError()
        version = value["calendar_version"]
        reference = value["reference"]
        if not isinstance(version, str) or not version or not isinstance(reference, str) or not reference.startswith("https://"):
            raise CalendarError()
        start, end = _date(value["valid_from"]), _date(value["valid_until"])
        weekday = value["publication_weekday"]
        if start > end or isinstance(weekday, bool) or not isinstance(weekday, int) or not 0 <= weekday <= 6:
            raise CalendarError()
        cutoff = value["cutoff"]
        days = cutoff["days_after_edition"]
        if isinstance(days, bool) or not isinstance(days, int) or not 0 <= days < 7:
            raise CalendarError()
        cutoff_time = time.fromisoformat(cutoff["time"])
        if cutoff_time.tzinfo is not None:
            raise CalendarError()
        zone = ZoneInfo(cutoff["timezone"])
        entries = value["exceptions"]
        if not isinstance(entries, list):
            raise CalendarError()
        overrides: list[tuple[date, date | None]] = []
        seen: set[date] = set()
        for item in entries:
            edition = _date(item["edition_date"])
            if not start <= edition <= end or edition.weekday() != weekday or edition in seen:
                raise CalendarError()
            seen.add(edition)
            if not isinstance(item["reference"], str) or not item["reference"].startswith("https://"):
                raise CalendarError()
            if item["kind"] == "no_edition":
                replacement = None
            elif item["kind"] == "moved":
                replacement = _date(item["publication_date"])
                if not start <= replacement <= end:
                    raise CalendarError()
            else:
                raise CalendarError()
            overrides.append((edition, replacement))
        calendar = EditionCalendar(version, start, end, weekday, zone, days, cutoff_time, tuple(overrides))
        # Reject two editions mapped to one date; such an override is ambiguous.
        all_dates = []
        cursor = start + timedelta(days=(weekday - start.weekday()) % 7)
        while cursor <= end:
            replacement = dict(overrides).get(cursor, cursor)
            if replacement is not None:
                all_dates.append(replacement)
            cursor += timedelta(days=7)
        if len(all_dates) != len(set(all_dates)):
            raise CalendarError()
        return calendar
    except CalendarError:
        raise
    except (KeyError, TypeError, ValueError):
        raise CalendarError() from None


def load_calendar(path: Path = DEFAULT_CALENDAR_PATH) -> EditionCalendar:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise CalendarError() from None
    return calendar_from_dict(value)


@dataclass(frozen=True)
class FreshnessAssessment:
    state: FreshnessState
    expected_date: str
    actual_date: str | None
    cutoff: str
    checked_at: str
    source_age_days: int | None
    calendar_version: str
    last_valid_date: str | None = None
    reason: str | None = None


def assess_publication(
    ranking_date: str | None,
    *,
    now: datetime,
    calendar: EditionCalendar,
    last_valid_date: str | None = None,
) -> FreshnessAssessment:
    instant = _aware(now)
    local_today = instant.astimezone(calendar.cutoff_zone).date()
    editions = calendar.editions(local_today)
    if not editions:
        raise CalendarError()
    expected = editions[-1]
    cutoff = calendar.cutoff_for(expected)
    reason = None
    age = None
    try:
        actual = _date(ranking_date)
        age = (local_today - actual).days
        if actual > local_today:
            reason = "ranking_source_future"
        elif actual not in editions:
            reason = "ranking_source_edition_invalid"
        elif last_valid_date and actual < _date(last_valid_date):
            reason = "ranking_source_stale"
    except CalendarError:
        actual = None
        reason = "ranking_source_schema_changed"
    if reason:
        state = FreshnessState.SOURCE_ERROR
    elif actual == expected:
        state = FreshnessState.FRESH
    else:
        # An older edition with an already-expired deadline stays stale even
        # when a newer week's publication grace period has just begun.
        due = [edition for edition in editions if calendar.cutoff_for(edition) <= instant]
        state = FreshnessState.STALE if due and actual < due[-1] else FreshnessState.PENDING_PUBLICATION
        if state == FreshnessState.STALE:
            expected = due[-1]
            cutoff = calendar.cutoff_for(expected)
    return FreshnessAssessment(
        state=state,
        expected_date=expected.isoformat(),
        actual_date=actual.isoformat() if actual else None,
        cutoff=cutoff.isoformat().replace("+00:00", "Z"),
        checked_at=instant.isoformat().replace("+00:00", "Z"),
        source_age_days=age,
        calendar_version=calendar.version,
        last_valid_date=last_valid_date,
        reason=reason,
    )
