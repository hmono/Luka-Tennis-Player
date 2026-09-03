"""Isolated Playwright adapter for the dynamically rendered ATP profile."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Mapping, Protocol

from .domain import (
    PLAYER_ATP_ID,
    PLAYER_NAME,
    DisciplineRanking,
    DomainValidationError,
    RankingObservation,
    snapshot_id,
)

PROFILE_SLUG = "luka-bojicic-ono"
PROFILE_ROOT = f"https://www.atptour.com/en/players/{PROFILE_SLUG}/{PLAYER_ATP_ID.lower()}"
HISTORY_URL = f"{PROFILE_ROOT}/rankings-history"
BREAKDOWN_URL = f"{PROFILE_ROOT}/rankings-breakdown?team={{discipline}}"


class RankingSource(Protocol):
    def fetch(self) -> RankingObservation: ...


class AtpSourceError(RuntimeError):
    """An ATP source failure with no payload, URL, or browser details."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _date_value(value: Any) -> str:
    if not isinstance(value, str):
        raise AtpSourceError("atp_incomplete_observation")
    normalized = value.strip().replace("/", "-").replace(".", "-")
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError:
        raise AtpSourceError("atp_incomplete_observation") from None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        raise AtpSourceError("atp_incomplete_observation")
    return parsed.isoformat()


def _integer(value: Any, *, rank: bool = False) -> int | None:
    if value is None and rank:
        return None
    if isinstance(value, bool):
        raise AtpSourceError("atp_incomplete_observation")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        text = value.strip().lstrip("#").replace(" ", "")
        if not re.fullmatch(r"[0-9][0-9.,]*", text):
            raise AtpSourceError("atp_incomplete_observation")
        separators = text.count(".") + text.count(",")
        if separators:
            groups = re.split(r"[.,]", text)
            if any(not group for group in groups) or any(len(group) != 3 for group in groups[1:]):
                raise AtpSourceError("atp_incomplete_observation")
            text = "".join(groups)
        number = int(text)
    else:
        raise AtpSourceError("atp_incomplete_observation")
    if rank and number == 0:
        return None
    if number < (1 if rank else 0):
        raise AtpSourceError("atp_incomplete_observation")
    return number


def _discipline(value: Any) -> DisciplineRanking:
    required = {"rank", "points", "career_high_rank", "career_high_date"}
    if not isinstance(value, Mapping):
        raise AtpSourceError("atp_incomplete_observation")
    if not required.issubset(value):
        raise AtpSourceError("atp_incomplete_observation")
    if set(value) != required:
        raise AtpSourceError("atp_schema_changed")
    high_rank = _integer(value["career_high_rank"], rank=True)
    high_date = value["career_high_date"]
    if high_date is not None:
        high_date = _date_value(high_date)
    try:
        return DisciplineRanking(
            rank=_integer(value["rank"], rank=True),
            points=_integer(value["points"], rank=False),  # type: ignore[arg-type]
            career_high_rank=high_rank,
            career_high_date=high_date,
        )
    except DomainValidationError as exc:
        code = "atp_identity_mismatch" if exc.code == "atp_identity_mismatch" else "atp_incomplete_observation"
        raise AtpSourceError(code) from None


def normalize_payload(payload: Any) -> RankingObservation:
    """Normalize the small, versioned payload contract captured in fixtures.

    The strict shape is intentional: an unreviewed ATP response change must
    stop collection instead of silently selecting plausible-looking numbers.
    """

    required = {"schema_version", "player", "ranking_date", "rankings"}
    if not isinstance(payload, Mapping) or set(payload) != required or payload.get("schema_version") != 1:
        raise AtpSourceError("atp_schema_changed")
    player = payload.get("player")
    rankings = payload.get("rankings")
    if not isinstance(player, Mapping) or set(player) != {"atp_id", "name"}:
        raise AtpSourceError("atp_schema_changed")
    if not isinstance(rankings, Mapping):
        raise AtpSourceError("atp_incomplete_observation")
    if set(rankings) != {"singles", "doubles"}:
        if "doubles" not in rankings or "singles" not in rankings:
            raise AtpSourceError("atp_incomplete_observation")
        raise AtpSourceError("atp_schema_changed")
    try:
        return RankingObservation(
            atp_id=player["atp_id"],
            name=player["name"],
            ranking_date=_date_value(payload["ranking_date"]),
            source="atptour",
            singles=_discipline(rankings["singles"]),
            doubles=_discipline(rankings["doubles"]),
        )
    except DomainValidationError as exc:
        code = "atp_identity_mismatch" if exc.code == "atp_identity_mismatch" else "atp_incomplete_observation"
        raise AtpSourceError(code) from None


def load_fixture(path: str) -> RankingObservation:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        raise AtpSourceError("invalid_fixture") from None
    return normalize_payload(payload)


def _first(patterns: tuple[str, ...], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1)
    return None


def _dom_discipline(text: str) -> DisciplineRanking:
    # The breakdown block follows the page's Refresh control. Anchoring there
    # avoids confusing it with the profile header's other discipline.
    current = re.search(
        r"Refresh\s+([0-9.,]+)\s+Rank\s+([0-9.,]+)\s+Points\b",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if current is None:
        raise AtpSourceError("atp_incomplete_observation")
    high_rank = _first(
        (
            r"Career\s+([0-9.,]+)\s+Career High Rank",
            r"Career High Rank\s*[:(][^\n)]*\)?\s*[:]?\s*([0-9.,]+)",
        ),
        text,
    )
    high_date = _first(
        (
            r"Career High Rank\s*\(([0-9]{4}[./-][0-9]{2}[./-][0-9]{2})\)",
            r"Career\s+[0-9.,]+\s+Career High Rank\s*\(([0-9]{4}[./-][0-9]{2}[./-][0-9]{2})\)",
        ),
        text,
    )
    return DisciplineRanking(
        rank=_integer(current.group(1), rank=True),
        points=_integer(current.group(2), rank=False),  # type: ignore[arg-type]
        career_high_rank=_integer(high_rank, rank=True) if high_rank is not None else None,
        career_high_date=_date_value(high_date) if high_date is not None else None,
    )


def normalize_dom(*, singles_text: str, doubles_text: str, history_text: str) -> RankingObservation:
    combined = "\n".join((singles_text[:3000], doubles_text[:3000], history_text[:3000]))
    if PLAYER_NAME.casefold() not in combined.casefold():
        raise AtpSourceError("atp_identity_mismatch")
    ranking_date = _first((r"\b([0-9]{4}[./-][0-9]{2}[./-][0-9]{2})\b",), history_text)
    if ranking_date is None:
        raise AtpSourceError("atp_incomplete_observation")
    try:
        return RankingObservation(
            atp_id=PLAYER_ATP_ID,
            name=PLAYER_NAME,
            ranking_date=_date_value(ranking_date),
            source="atptour",
            singles=_dom_discipline(singles_text),
            doubles=_dom_discipline(doubles_text),
        )
    except DomainValidationError:
        raise AtpSourceError("atp_incomplete_observation") from None


class AtpRankingSource:
    """Collect a complete observation from official ATP pages using Chromium."""

    def __init__(self, *, timeout_ms: int = 60_000, headless: bool = True) -> None:
        self.timeout_ms = timeout_ms
        self.headless = headless

    def fetch(self) -> RankingObservation:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise AtpSourceError("atp_source_unavailable") from None

        intercepted: list[RankingObservation] = []
        texts: dict[str, str] = {}
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 1000},
                )
                page = context.new_page()

                def capture(response: Any) -> None:
                    if response.status != 200 or "rank" not in response.url.casefold():
                        return
                    content_type = (response.headers.get("content-type") or "").casefold()
                    if "json" not in content_type:
                        return
                    try:
                        intercepted.append(normalize_payload(response.json()))
                    except (AtpSourceError, ValueError):
                        return

                page.on("response", capture)
                for discipline in ("singles", "doubles"):
                    page.goto(
                        BREAKDOWN_URL.format(discipline=discipline),
                        wait_until="networkidle",
                        timeout=self.timeout_ms,
                    )
                    texts[discipline] = page.locator("body").inner_text(timeout=self.timeout_ms)
                page.goto(HISTORY_URL, wait_until="networkidle", timeout=self.timeout_ms)
                texts["history"] = page.locator("body").inner_text(timeout=self.timeout_ms)
                browser.close()
        except PlaywrightTimeoutError:
            raise AtpSourceError("atp_source_timeout") from None
        except AtpSourceError:
            raise
        except Exception:
            raise AtpSourceError("atp_source_failed") from None

        unique = {snapshot_id(item): item for item in intercepted}
        if len(unique) > 1:
            raise AtpSourceError("atp_schema_changed")
        if unique:
            return next(iter(unique.values()))
        return normalize_dom(
            singles_text=texts.get("singles", ""),
            doubles_text=texts.get("doubles", ""),
            history_text=texts.get("history", ""),
        )
