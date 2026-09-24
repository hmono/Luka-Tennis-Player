"""ITF player-profile source for the athlete's official ATP rankings.

The ITF profile API republishes the ATP singles and doubles rankings (rank and
official ranking date, no points).  Access mirrors ``scripts/update_career.py``:
a headless Chromium session loads the public profile page so the site's
cookies are set, then the two ``GetPlayerOverview`` JSON endpoints are read.

Every failure surfaces as a stable ``RankingSourceError`` code; no response
bodies, headers, or cookies are logged.  Nothing is persisted here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping

from .domain import PLAYER_ATP_ID, PLAYER_NAME, normalize_player_name
from .source import RankingSourceError, RawDisciplineRanking, RawRankingObservation

SOURCE_NAME = "itf"

# Versioned identity crosswalk: the ITF profile id that belongs to ATP B0UF.
# Verified 2026-09-24 against the profile page title and the ATP rank/date.
ITF_PLAYER_ID = "800625103"
ITF_BASE_URL = "https://www.itftennis.com"
PROFILE_PATH = f"/en/players/luka-bojicic-ono/{ITF_PLAYER_ID}/bra/mt/s/overview/"
OVERVIEW_PATH = "/tennis/api/PlayerApi/GetPlayerOverview"
MATCH_TYPE_CODES: Mapping[str, str] = {"singles": "S", "doubles": "D"}
RANKING_NAMES: Mapping[str, str] = {
    "singles": "ATP Singles Ranking",
    "doubles": "ATP Doubles Ranking",
}
DEFAULT_TIMEOUT_SECONDS = 60.0
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def overview_path(discipline: str) -> str:
    return (
        f"{OVERVIEW_PATH}?circuitCode=MT&matchTypeCode={MATCH_TYPE_CODES[discipline]}"
        f"&playerId={ITF_PLAYER_ID}"
    )


@dataclass(frozen=True, kw_only=True)
class ItfOverviewResponse:
    """One decoded ``GetPlayerOverview`` reply; ``payload`` is None if not JSON."""

    status: int
    payload: Any


@dataclass(frozen=True, kw_only=True)
class ItfProfileCapture:
    """Everything the parser needs, captured in one browser session."""

    page_title: str
    singles: ItfOverviewResponse
    doubles: ItfOverviewResponse


def _http_error_code(status: int) -> str:
    if status == 401:
        return "ranking_source_authentication"
    if status == 403:
        return "ranking_source_blocked"
    if status == 429:
        return "ranking_source_rate_limited"
    if status == 408:
        return "ranking_source_timeout"
    return "ranking_source_incomplete"


def _ranking_date(value: Any) -> str:
    """ITF publishes ``21 September 2026``; return ISO or fail closed."""

    if not isinstance(value, str):
        raise RankingSourceError("ranking_source_schema_changed")
    try:
        return datetime.strptime(value.strip(), "%d %B %Y").date().isoformat()
    except ValueError:
        raise RankingSourceError("ranking_source_schema_changed") from None


def _discipline(response: ItfOverviewResponse, discipline: str) -> tuple[RawDisciplineRanking, str | None]:
    if response.status != 200:
        raise RankingSourceError(_http_error_code(response.status))
    payload = response.payload
    if not isinstance(payload, Mapping) or not isinstance(payload.get("rankings"), list):
        raise RankingSourceError("ranking_source_schema_changed")
    entries = [
        entry
        for entry in payload["rankings"]
        if isinstance(entry, Mapping) and entry.get("name") == RANKING_NAMES[discipline]
    ]
    if len(entries) > 1:
        raise RankingSourceError("ranking_source_schema_changed")
    if not entries:
        # A well-formed reply without the ATP entry: the player is not ranked
        # in this discipline. A malformed reply never reaches this branch.
        return RawDisciplineRanking(status="unranked", rank=None, points=None), None
    entry = entries[0]
    rank = entry.get("rank")
    ranking_date = _ranking_date(entry.get("date"))
    if rank is None:
        return RawDisciplineRanking(status="unranked", rank=None, points=None), ranking_date
    if isinstance(rank, bool) or not isinstance(rank, int) or rank <= 0:
        raise RankingSourceError("ranking_source_schema_changed")
    return RawDisciplineRanking(status="ranked", rank=rank, points=None), ranking_date


def parse_capture(capture: ItfProfileCapture) -> RawRankingObservation:
    """Validate a capture and return the raw observation, or fail closed."""

    if normalize_player_name(PLAYER_NAME) not in normalize_player_name(capture.page_title):
        raise RankingSourceError("ranking_source_identity_mismatch")
    singles, singles_date = _discipline(capture.singles, "singles")
    doubles, doubles_date = _discipline(capture.doubles, "doubles")
    dates = {value for value in (singles_date, doubles_date) if value is not None}
    if len(dates) != 1:
        # No official date at all, or singles and doubles from different
        # publications: neither can be persisted as one observation.
        raise RankingSourceError("ranking_source_incomplete")
    return RawRankingObservation(
        source=SOURCE_NAME,
        atp_id=PLAYER_ATP_ID,
        name=PLAYER_NAME,
        ranking_date=dates.pop(),
        singles=singles,
        doubles=doubles,
    )


def capture_profile(timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> ItfProfileCapture:
    """Load the profile in headless Chromium and read both overview endpoints."""

    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    timeout_ms = int(timeout_seconds * 1000)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 800})
            page = context.new_page()
            try:
                # ``networkidle`` is unreliable on the ITF site (third-party
                # beacons keep the network busy). Wait only for the document
                # plus the first profile API reply, which proves the session
                # cookies are in place.
                with page.expect_response(
                    lambda response: "/tennis/api/" in response.url, timeout=timeout_ms
                ) as first_api_reply:
                    page.goto(ITF_BASE_URL + PROFILE_PATH, timeout=timeout_ms, wait_until="domcontentloaded")
                first_api_reply.value
            except PlaywrightTimeout:
                # The session cookies may already be set; the API calls decide.
                pass
            title = page.title()
            responses: dict[str, ItfOverviewResponse] = {}
            for discipline in ("singles", "doubles"):
                reply = context.request.get(ITF_BASE_URL + overview_path(discipline), timeout=timeout_ms)
                try:
                    payload = reply.json()
                except Exception:  # noqa: BLE001 - any non-JSON body is treated alike
                    payload = None
                responses[discipline] = ItfOverviewResponse(status=reply.status, payload=payload)
        finally:
            browser.close()
    return ItfProfileCapture(page_title=title, singles=responses["singles"], doubles=responses["doubles"])


class ItfRankingSource:
    """``RankingSource`` implementation backed by the ITF player profile."""

    name = SOURCE_NAME

    def __init__(
        self,
        *,
        capture: Callable[[float], ItfProfileCapture] = capture_profile,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._capture = capture
        self._timeout_seconds = timeout_seconds

    def fetch(self) -> RawRankingObservation:
        try:
            capture = self._capture(self._timeout_seconds)
        except RankingSourceError:
            raise
        except Exception as exc:  # noqa: BLE001 - redact browser/network details
            code = "ranking_source_timeout" if "timeout" in type(exc).__name__.casefold() else "ranking_source_incomplete"
            raise RankingSourceError(code) from None
        return parse_capture(capture)
