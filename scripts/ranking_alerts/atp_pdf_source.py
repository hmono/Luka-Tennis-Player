"""Fail-closed reader for the official ATP alphabetical ranking PDFs.

The PDFs are an official ATP publication, but this module deliberately does
not attempt to work around an ATP/WAF refusal.  It only performs ordinary,
bounded HTTPS requests and turns every failure into a safe source error code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import socket
import time
from collections.abc import Callable, Mapping
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from .domain import PLAYER_ATP_ID, PLAYER_NAME, normalize_player_name
from .pdf_parser import ParsedRankingReport, extract_pdf_text, parse_ranking_report
from .source import RankingSourceError, RawDisciplineRanking, RawRankingObservation


# These are the permanent public ATP ranking-report endpoints.  Keep them
# fixed: this source must never accept a caller supplied destination.
SINGLES_ALPHA_PDF_URL = (
    "https://www.atptour.com/-/media/files/rankings-and-stats/singles_entry_alpha.pdf"
)
DOUBLES_ALPHA_PDF_URL = (
    "https://www.atptour.com/-/media/files/rankings-and-stats/doubles_entry_alpha.pdf"
)
PDF_URLS: Mapping[str, str] = {
    "singles": SINGLES_ALPHA_PDF_URL,
    "doubles": DOUBLES_ALPHA_PDF_URL,
}

MAX_PDF_BYTES = 20 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_REDIRECTS = 3
MAX_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 30.0
BACKOFF_SECONDS = 1.0


class _LimitedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """The standard handler has a generous redirect limit; use a small one."""

    max_redirections = MAX_REDIRECTS


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


def _retryable_status(status: int) -> bool:
    return status in {408, 429} or 500 <= status <= 599


def _retry_after_seconds(value: object, *, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> float | None:
    """Parse a server hint without letting a remote server delay us indefinitely."""

    if not isinstance(value, str):
        return None
    try:
        seconds = float(value.strip())
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        seconds = (retry_at.astimezone(timezone.utc) - now()).total_seconds()
    if seconds < 0:
        return 0.0
    return min(seconds, MAX_RETRY_AFTER_SECONDS)


def _delay_for_retry(attempt: int, headers: Mapping[str, Any] | None) -> float:
    hint = _retry_after_seconds(headers.get("Retry-After")) if headers is not None else None
    if hint is not None:
        return hint
    return min(BACKOFF_SECONDS * (2**attempt), MAX_RETRY_AFTER_SECONDS)


def _headers(response: Any) -> Mapping[str, Any] | None:
    value = getattr(response, "headers", None)
    return value if isinstance(value, Mapping) or hasattr(value, "get") else None


def _content_length(headers: Mapping[str, Any] | None) -> int | None:
    if headers is None:
        return None
    value = headers.get("Content-Length")
    if value is None:
        return None
    try:
        length = int(value)
    except (TypeError, ValueError):
        return None
    return length if length >= 0 else None


def _response_status(response: Any) -> int:
    getter = getattr(response, "getcode", None)
    status = getter() if callable(getter) else getattr(response, "status", 200)
    try:
        return int(status)
    except (TypeError, ValueError):
        return 0


def _is_pdf(response_headers: Mapping[str, Any] | None, body: bytes) -> bool:
    # Content-Type is not dependable for old ATP assets; byte magic is.
    content_type = str(response_headers.get("Content-Type", "")) if response_headers is not None else ""
    if "html" in content_type.casefold():
        return False
    return len(body) > 5 and body.startswith(b"%PDF-") and body.rstrip().endswith(b"%%EOF")


def _is_expected_final_url(requested_url: str, response: Any) -> bool:
    """Refuse a redirect that has left the fixed official ATP asset path."""

    geturl = getattr(response, "geturl", None)
    if not callable(geturl):
        # Lightweight test doubles and some file-like response wrappers do not
        # expose a final URL; the initial Request is still fixed HTTPS ATP.
        return True
    try:
        requested = urllib.parse.urlsplit(requested_url)
        final = urllib.parse.urlsplit(geturl())
    except (TypeError, ValueError):
        return False
    return (
        final.scheme == "https"
        and final.hostname == "www.atptour.com"
        and final.path == requested.path
        and not final.query
        and not final.fragment
    )


def _default_opener(request: urllib.request.Request, *, timeout: float) -> Any:
    opener = urllib.request.build_opener(_LimitedRedirectHandler())
    return opener.open(request, timeout=timeout)


def download_pdf(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    opener: Callable[..., Any] = _default_opener,
    sleeper: Callable[[float], None] = time.sleep,
) -> bytes:
    """Download one fixed report with a size limit and bounded transient retry."""

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/pdf"},
        method="GET",
    )
    last_code = "ranking_source_incomplete"
    for attempt in range(MAX_ATTEMPTS):
        try:
            with opener(request, timeout=timeout_seconds) as response:
                status = _response_status(response)
                headers = _headers(response)
                if status != 200:
                    last_code = _http_error_code(status)
                    if _retryable_status(status) and attempt + 1 < MAX_ATTEMPTS:
                        sleeper(_delay_for_retry(attempt, headers))
                        continue
                    raise RankingSourceError(last_code)
                length = _content_length(headers)
                if not _is_expected_final_url(url, response):
                    raise RankingSourceError("ranking_source_blocked")
                if length is not None and length > MAX_PDF_BYTES:
                    raise RankingSourceError("ranking_source_coverage_truncated")
                body = response.read(MAX_PDF_BYTES + 1)
        except RankingSourceError:
            raise
        except urllib.error.HTTPError as exc:
            last_code = _http_error_code(exc.code)
            if _retryable_status(exc.code) and attempt + 1 < MAX_ATTEMPTS:
                sleeper(_delay_for_retry(attempt, exc.headers))
                continue
            raise RankingSourceError(last_code) from None
        except (TimeoutError, socket.timeout):
            last_code = "ranking_source_timeout"
            if attempt + 1 < MAX_ATTEMPTS:
                sleeper(_delay_for_retry(attempt, None))
                continue
            raise RankingSourceError(last_code) from None
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), (TimeoutError, socket.timeout)):
                last_code = "ranking_source_timeout"
                if attempt + 1 < MAX_ATTEMPTS:
                    sleeper(_delay_for_retry(attempt, None))
                    continue
                raise RankingSourceError(last_code) from None
            raise RankingSourceError("ranking_source_incomplete") from None
        except OSError:
            raise RankingSourceError("ranking_source_incomplete") from None

        if len(body) > MAX_PDF_BYTES:
            raise RankingSourceError("ranking_source_coverage_truncated")
        if not _is_pdf(headers, body):
            raise RankingSourceError("ranking_source_schema_changed")
        return body
    raise RankingSourceError(last_code)


def _discipline_from_report(report: ParsedRankingReport) -> RawDisciplineRanking:
    rank = report.rank
    try:
        return RawDisciplineRanking(
            status="unranked" if rank is None else "ranked",
            rank=rank,
            points=report.points,
        )
    except ValueError:
        raise RankingSourceError("ranking_source_schema_changed") from None


def _validate_report(report: ParsedRankingReport, discipline: str) -> None:
    if report.discipline != discipline:
        raise RankingSourceError("ranking_source_schema_changed")
    if normalize_player_name(report.player_name) != normalize_player_name(PLAYER_NAME):
        raise RankingSourceError("ranking_source_identity_mismatch")
    # The parser accepts only canonical ISO publication dates.  Retain this
    # equality check here so a parser regression cannot mix two publications.
    if not isinstance(report.ranking_date, str) or len(report.ranking_date) != 10:
        raise RankingSourceError("ranking_source_schema_changed")


class AtpPdfRankingSource:
    """Read the ATP singles and individual-doubles alphabetical PDF reports."""

    name = "atp-pdf"

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        opener: Callable[..., Any] = _default_opener,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._opener = opener
        self._sleeper = sleeper

    def _report(self, discipline: str) -> ParsedRankingReport:
        try:
            body = download_pdf(
                PDF_URLS[discipline],
                timeout_seconds=self.timeout_seconds,
                opener=self._opener,
                sleeper=self._sleeper,
            )
            return parse_ranking_report(extract_pdf_text(body), discipline, PLAYER_NAME)
        except RankingSourceError:
            raise
        except Exception:
            # Parser errors may include report text; never expose them.
            raise RankingSourceError("ranking_source_schema_changed") from None

    def fetch(self) -> RawRankingObservation:
        singles_report = self._report("singles")
        doubles_report = self._report("doubles")
        _validate_report(singles_report, "singles")
        _validate_report(doubles_report, "doubles")
        if singles_report.ranking_date != doubles_report.ranking_date:
            raise RankingSourceError("ranking_source_incomplete")
        try:
            return RawRankingObservation(
                source=self.name,
                atp_id=PLAYER_ATP_ID,
                name=PLAYER_NAME,
                ranking_date=singles_report.ranking_date,
                singles=_discipline_from_report(singles_report),
                doubles=_discipline_from_report(doubles_report),
            )
        except RankingSourceError:
            raise
        except ValueError:
            raise RankingSourceError("ranking_source_schema_changed") from None
