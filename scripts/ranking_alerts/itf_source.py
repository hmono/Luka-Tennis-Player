"""ITF player-profile source for the athlete's official ATP rankings.

The ITF profile API republishes the ATP singles and doubles rankings (rank and
official ranking date, no points).  Access mirrors ``scripts/update_career.py``:
a headless Chromium session loads the public profile page so the site's
cookies are set, then the two ``GetPlayerOverview`` JSON endpoints are read.

Every failure surfaces as a stable ``RankingSourceError`` code. Only bounded,
allowlisted diagnostic metadata is exposed; bodies and cookies stay private.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

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
    retrieved_at: str | None = None
    cache_headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class ItfProfileCapture:
    """Everything the parser needs, captured in one browser session."""

    page_title: str
    singles: ItfOverviewResponse
    doubles: ItfOverviewResponse
    navigation_status: int | None = None
    final_url: str | None = None
    dom_identity: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    navigation_error: str | None = None
    cache_headers: Mapping[str, str] = field(default_factory=dict)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cache_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Never include Set-Cookie, authorization, arbitrary headers or bodies."""
    lowered = {key.lower(): value for key, value in headers.items()}
    return {
        key: lowered[key.lower()]
        for key in ("Date", "Age", "ETag", "Cache-Control", "Last-Modified")
        if key.lower() in lowered and isinstance(lowered[key.lower()], str)
        and len(lowered[key.lower()]) <= 256
        and all(32 <= ord(char) < 127 for char in lowered[key.lower()])
    }


def _is_profile_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.netloc == "www.itftennis.com" and parts.path.rstrip("/") == PROFILE_PATH.rstrip("/")


def _safe_url(url: str | None) -> str | None:
    if url is None:
        return None
    # Queries, fragments, userinfo and unknown paths may contain secrets.
    return ITF_BASE_URL + PROFILE_PATH if _is_profile_url(url) else "[unexpected URL redacted]"


def _identity_matches(value: str | None) -> bool:
    if not value:
        return False
    actual = normalize_player_name(value)
    expected = normalize_player_name(PLAYER_NAME)
    return actual == expected or actual.startswith(expected + " ")


def _dom_identity_matches(value: str | None) -> bool:
    """Match the whole athlete heading, allowing only known ITF UI suffixes."""
    actual = normalize_player_name(value)
    expected = normalize_player_name(PLAYER_NAME)
    return actual in {
        expected,
        expected + " men's singles overview",
        expected + " men's doubles overview",
    }


def _page_kind(title: str) -> str:
    if _identity_matches(title):
        return "athlete_profile"
    normalized = title.casefold()
    if any(marker in normalized for marker in ("access denied", "just a moment", "verify", "captcha", "blocked", "forbidden")):
        return "blocked"
    return "unknown"


def capture_telemetry(capture: ItfProfileCapture) -> dict[str, Any]:
    """Safe metadata interface used by CLI/Actions on success and failure."""
    kind = _page_kind(capture.page_title)
    result: dict[str, Any] = {
        "source": SOURCE_NAME, "atp_id": PLAYER_ATP_ID, "itf_player_id": ITF_PLAYER_ID,
        "started_at": capture.started_at, "completed_at": capture.completed_at,
        "navigation_status": capture.navigation_status,
        "navigation_error": capture.navigation_error,
        "final_url": _safe_url(capture.final_url),
        "page_title": "Luka Bojicic Ono Tennis Player Profile | ITF" if kind == "athlete_profile" else f"[{kind} title redacted]",
        "page_kind": kind,
        "dom_identity": PLAYER_NAME if _dom_identity_matches(capture.dom_identity) else ("missing" if not capture.dom_identity else "other"),
        "cache_headers": _cache_headers(capture.cache_headers),
    }
    for discipline in ("singles", "doubles"):
        reply = getattr(capture, discipline)
        try:
            ranking, edition = _discipline(reply, discipline)
            rank = ranking.rank
        except RankingSourceError:
            edition = None
            rank = None
        result[discipline] = {
            "http_status": reply.status, "retrieved_at": reply.retrieved_at,
            "ranking_date": edition, "cache_headers": _cache_headers(reply.cache_headers),
            "rank": rank,
            "json_object": isinstance(reply.payload, Mapping),
        }
    return result


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
        # Missing coverage provides neither an unranked fact nor an edition.
        # Never borrow the other discipline's date to complete an observation.
        raise RankingSourceError("ranking_source_incomplete")
    entry = entries[0]
    if "rank" not in entry:
        raise RankingSourceError("ranking_source_schema_changed")
    rank = entry.get("rank")
    ranking_date = _ranking_date(entry.get("date"))
    if rank is None:
        return RawDisciplineRanking(status="unranked", rank=None, points=None), ranking_date
    if isinstance(rank, bool) or not isinstance(rank, int) or rank <= 0:
        raise RankingSourceError("ranking_source_schema_changed")
    return RawDisciplineRanking(status="ranked", rank=rank, points=None), ranking_date


def parse_capture(capture: ItfProfileCapture) -> RawRankingObservation:
    """Validate a capture and return the raw observation, or fail closed."""

    if capture.navigation_status is not None and capture.navigation_status != 200:
        raise RankingSourceError(_http_error_code(capture.navigation_status))
    if capture.navigation_error:
        raise RankingSourceError(capture.navigation_error)
    if capture.final_url is not None and not _is_profile_url(capture.final_url):
        raise RankingSourceError("ranking_source_redirect")
    if _page_kind(capture.page_title) == "blocked":
        raise RankingSourceError("ranking_source_blocked")
    # Structural/API failures must not be misreported as another athlete.
    if capture.singles.status != 200 or capture.doubles.status != 200:
        failing = capture.singles if capture.singles.status != 200 else capture.doubles
        raise RankingSourceError(_http_error_code(failing.status))
    if capture.singles.payload is None or capture.doubles.payload is None:
        raise RankingSourceError("ranking_source_schema_changed")
    if not _identity_matches(capture.page_title):
        raise RankingSourceError("ranking_source_identity_mismatch")
    if capture.final_url is not None and not capture.dom_identity:
        raise RankingSourceError("ranking_source_incomplete")
    if capture.dom_identity is not None and not _dom_identity_matches(capture.dom_identity):
        raise RankingSourceError("ranking_source_identity_mismatch")
    singles, singles_date = _discipline(capture.singles, "singles")
    doubles, doubles_date = _discipline(capture.doubles, "doubles")
    if singles_date is None or doubles_date is None or singles_date != doubles_date:
        # Both disciplines must explicitly confirm the same publication.
        raise RankingSourceError("ranking_source_incomplete")
    return RawRankingObservation(
        source=SOURCE_NAME,
        atp_id=PLAYER_ATP_ID,
        name=PLAYER_NAME,
        ranking_date=singles_date,
        singles=singles,
        doubles=doubles,
    )


def capture_profile(timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> ItfProfileCapture:
    """Load the profile in headless Chromium and read both overview endpoints."""

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RankingSourceError("ranking_source_dependency") from None

    timeout_ms = int(timeout_seconds * 1000)
    started_at = _utc_now()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 800})
            page = context.new_page()
            navigation = None
            navigation_error = None
            try:
                # ``networkidle`` is unreliable on the ITF site (third-party
                # beacons keep the network busy). Wait only for the document
                # plus the first profile API reply, which proves the session
                # cookies are in place.
                with page.expect_response(
                    lambda response: OVERVIEW_PATH in response.url, timeout=timeout_ms
                ) as first_api_reply:
                    navigation = page.goto(ITF_BASE_URL + PROFILE_PATH, timeout=timeout_ms, wait_until="domcontentloaded")
                first_api_reply.value
            except PlaywrightTimeout:
                # Timeout waiting for an API is different from failed navigation.
                if navigation is None:
                    navigation_error = "ranking_source_timeout"
            except Exception:
                navigation_error = "ranking_source_navigation"
            title = page.title()
            dom_identity = None
            if navigation_error is None and navigation is not None and navigation.status == 200:
                try:
                    page.locator("h1").first.wait_for(timeout=timeout_ms)
                    dom_identity = page.locator("h1").first.inner_text()
                except PlaywrightTimeout:
                    if _page_kind(title) != "blocked":
                        navigation_error = "ranking_source_incomplete"
            responses: dict[str, ItfOverviewResponse] = {}
            for discipline in ("singles", "doubles"):
                try:
                    reply = context.request.get(ITF_BASE_URL + overview_path(discipline), timeout=timeout_ms)
                    try:
                        payload = reply.json()
                    except Exception:
                        payload = None
                    responses[discipline] = ItfOverviewResponse(
                        status=reply.status, payload=payload,
                        retrieved_at=_utc_now(), cache_headers=_cache_headers(reply.headers),
                    )
                except Exception as exc:
                    # Preserve partial metadata without logging network details.
                    status = 408 if isinstance(exc, PlaywrightTimeout) else 0
                    responses[discipline] = ItfOverviewResponse(status=status, payload=None, retrieved_at=_utc_now())
            capture = ItfProfileCapture(
                page_title=title, singles=responses["singles"], doubles=responses["doubles"],
                navigation_status=navigation.status if navigation is not None else None,
                final_url=page.url, dom_identity=dom_identity,
                started_at=started_at, completed_at=_utc_now(), navigation_error=navigation_error,
                cache_headers=_cache_headers(navigation.headers) if navigation is not None else {},
            )
        finally:
            browser.close()
    return capture


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
        self.last_telemetry: dict[str, Any] = {}

    def fetch(self) -> RawRankingObservation:
        self.last_telemetry = {"source": SOURCE_NAME, "atp_id": PLAYER_ATP_ID, "started_at": _utc_now()}
        try:
            capture = self._capture(self._timeout_seconds)
            self.last_telemetry = capture_telemetry(capture)
            observation = parse_capture(capture)
            self.last_telemetry["source_ranking_date"] = observation.ranking_date
        except RankingSourceError as exc:
            self.last_telemetry.update({"error_code": exc.code, "completed_at": _utc_now()})
            raise
        except Exception as exc:  # noqa: BLE001 - redact browser/network details
            code = "ranking_source_timeout" if "timeout" in type(exc).__name__.casefold() else "ranking_source_incomplete"
            self.last_telemetry.update({"error_code": code, "completed_at": _utc_now()})
            raise RankingSourceError(code) from None
        return observation
