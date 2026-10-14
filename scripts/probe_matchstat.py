#!/usr/bin/env python3
"""Run a non-persistent, sanitized qualification probe for Matchstat.

The probe validates the latest official ATP ranking date and Luka's Brazilian
singles and doubles rows.  Matchstat uses its own player identifiers, so a
successful response remains pending manual review of the mapping to ATP ID
``B0UF``.  This module never writes files or promotes a production source.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, TextIO


API_KEY_ENV = "MATCHSTAT_RAPIDAPI_KEY"
API_HOST = "tennis-api-atp-wta-itf.p.rapidapi.com"
BASE_URL = f"https://{API_HOST}"
FILTERS_PATH = "/tennis/v2/ranking/atp/filters"
RANKINGS_PATH = "/tennis/v2/ranking/atp"
EXPECTED_ATP_ID = "B0UF"
EXPECTED_PLAYER_NAME = "Luka Bojicic Ono"
EXPECTED_COUNTRY = "BRA"
PAGE_SIZE = 100
MAX_PAGES = 20
MAX_RESPONSE_BYTES = 512 * 1024
MAX_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 30.0


def _normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(ascii_value.casefold().split())


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _error_code(status: int) -> str:
    if status == 401:
        return "ranking_source_authentication"
    if status == 403:
        return "ranking_source_blocked"
    if status == 429:
        return "ranking_source_rate_limited"
    return "ranking_source_incomplete"


def _retry_after_seconds(headers: Any, *, now: Callable[[], datetime]) -> float | None:
    if headers is None:
        return None
    raw = headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return max(0.0, min(float(raw), MAX_RETRY_AFTER_SECONDS))
    except (TypeError, ValueError):
        pass
    try:
        retry_at = parsedate_to_datetime(str(raw))
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, min((retry_at - now()).total_seconds(), MAX_RETRY_AFTER_SECONDS))
    except (TypeError, ValueError, OverflowError):
        return None


def _request_json(
    *,
    path: str,
    query: Mapping[str, str | int] | None,
    api_key: str,
    timeout_seconds: float,
    opener: Callable[..., Any],
    sleeper: Callable[[float], None],
    now: Callable[[], datetime],
) -> Any:
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={"X-RapidAPI-Host": API_HOST, "X-RapidAPI-Key": api_key},
        method="GET",
    )

    for attempt in range(MAX_ATTEMPTS):
        try:
            with opener(request, timeout=timeout_seconds) as response:
                status = int(response.getcode())
                body = response.read(MAX_RESPONSE_BYTES + 1)
                headers = getattr(response, "headers", None)
        except urllib.error.HTTPError as exc:
            if exc.code == 429 or 500 <= exc.code <= 599:
                if attempt + 1 < MAX_ATTEMPTS:
                    delay = _retry_after_seconds(exc.headers, now=now)
                    sleeper(delay if delay is not None else float(2**attempt))
                    continue
            raise RuntimeError(_error_code(exc.code)) from None
        except (TimeoutError, socket.timeout):
            if attempt + 1 < MAX_ATTEMPTS:
                sleeper(float(2**attempt))
                continue
            raise RuntimeError("ranking_source_timeout") from None
        except (urllib.error.URLError, OSError):
            raise RuntimeError("ranking_source_incomplete") from None

        if status == 429 or 500 <= status <= 599:
            if attempt + 1 < MAX_ATTEMPTS:
                delay = _retry_after_seconds(headers, now=now)
                sleeper(delay if delay is not None else float(2**attempt))
                continue
            raise RuntimeError(_error_code(status))
        if status != 200:
            raise RuntimeError(_error_code(status))
        if len(body) > MAX_RESPONSE_BYTES:
            raise RuntimeError("ranking_source_coverage_truncated")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("ranking_source_schema_changed") from None

    raise RuntimeError("ranking_source_incomplete")  # pragma: no cover


def _official_dates(payload: Any) -> tuple[datetime, ...]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("date"), list):
        raise RuntimeError("ranking_source_schema_changed")
    dates: set[datetime] = set()
    for raw in payload["date"]:
        if not isinstance(raw, str):
            raise RuntimeError("ranking_source_schema_changed")
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            raise RuntimeError("ranking_source_schema_changed") from None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        dates.add(value.astimezone(timezone.utc))
    if not dates:
        raise RuntimeError("ranking_source_incomplete")
    return tuple(sorted(dates, reverse=True))


def _parse_row(row: Any) -> tuple[int, int] | None:
    if not isinstance(row, Mapping):
        raise RuntimeError("ranking_source_schema_changed")
    player = row.get("player")
    if not isinstance(player, Mapping):
        raise RuntimeError("ranking_source_schema_changed")

    name = player.get("name")
    country = player.get("countryAcr")
    if not isinstance(name, str) or not isinstance(country, str):
        raise RuntimeError("ranking_source_schema_changed")
    if _normalize_name(name) != _normalize_name(EXPECTED_PLAYER_NAME):
        return None
    if country.upper() != EXPECTED_COUNTRY:
        raise RuntimeError("ranking_source_identity_mismatch")

    rank = row.get("position")
    points = row.get("pts")
    if not _is_int(rank) or rank <= 0 or not _is_int(points) or points < 0:
        raise RuntimeError("ranking_source_incomplete")
    return rank, points


def _fetch_discipline(
    *,
    discipline: str,
    official_date: datetime,
    api_key: str,
    timeout_seconds: float,
    opener: Callable[..., Any],
    sleeper: Callable[[float], None],
    now: Callable[[], datetime],
) -> tuple[int, int, int]:
    requested_date = official_date.strftime("%d.%m.%Y")
    matches: list[tuple[int, int]] = []
    fingerprints: set[str] = set()

    for page in range(1, MAX_PAGES + 1):
        payload = _request_json(
            path=RANKINGS_PATH,
            query={
                "group": discipline,
                "date": requested_date,
                "countryAcr": EXPECTED_COUNTRY,
                "page": page,
                "limit": PAGE_SIZE,
            },
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            opener=opener,
            sleeper=sleeper,
            now=now,
        )
        if not isinstance(payload, list):
            raise RuntimeError("ranking_source_schema_changed")
        if not payload:
            break
        fingerprint = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if fingerprint in fingerprints:
            raise RuntimeError("ranking_source_coverage_truncated")
        fingerprints.add(fingerprint)
        for row in payload:
            match = _parse_row(row)
            if match is not None:
                matches.append(match)
    else:
        raise RuntimeError("ranking_source_coverage_truncated")

    if len(matches) != 1:
        code = "ranking_source_identity_mismatch" if len(matches) > 1 else "ranking_source_incomplete"
        raise RuntimeError(code)
    return matches[0][0], matches[0][1], page


def _report_lines(
    *,
    status: str,
    detail: str,
    ranking_date: str | None = None,
    singles: tuple[int, int, int] | None = None,
    doubles: tuple[int, int, int] | None = None,
) -> tuple[str, ...]:
    lines = ["probe=matchstat", f"status={status}", f"detail={detail}"]
    if ranking_date is not None:
        lines.append(f"ranking_date={ranking_date}")
    if singles is not None:
        lines.extend((f"singles_rank={singles[0]}", f"singles_points={singles[1]}", f"singles_pages={singles[2]}"))
    if doubles is not None:
        lines.extend((f"doubles_rank={doubles[0]}", f"doubles_points={doubles[1]}", f"doubles_pages={doubles[2]}"))
    valid = status == "ok"
    lines.extend(
        (
            "gate_identity=pending_manual_review",
            f"gate_singles_individual={'pass' if valid else 'unverified'}",
            f"gate_doubles_individual={'pass' if valid else 'unverified'}",
            f"gate_official_ranking_date={'pass' if valid else 'unverified'}",
            "gate_atp_id_mapping=pending_manual_review",
            "gate_coverage_beyond_2000=pending_manual_review",
            "gate_two_publications=pending_manual_review",
            "decision=pending_manual_review" if valid else "decision=no-go",
        )
    )
    return tuple(lines)


def probe(
    *,
    api_key: str,
    timeout_seconds: float = 20.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> tuple[int, tuple[str, ...]]:
    """Run the qualification requests and return a sanitized report."""

    if not api_key:
        return 2, _report_lines(status="error", detail="ranking_source_authentication")
    if timeout_seconds <= 0:
        return 2, _report_lines(status="error", detail="ranking_source_incomplete")
    try:
        filters = _request_json(
            path=FILTERS_PATH,
            query=None,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            opener=opener,
            sleeper=sleeper,
            now=now,
        )
        official_date = _official_dates(filters)[0]
        singles = _fetch_discipline(
            discipline="singles",
            official_date=official_date,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            opener=opener,
            sleeper=sleeper,
            now=now,
        )
        doubles = _fetch_discipline(
            discipline="doubles",
            official_date=official_date,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            opener=opener,
            sleeper=sleeper,
            now=now,
        )
    except RuntimeError as exc:
        detail = str(exc)
        if not detail.startswith("ranking_source_"):
            detail = "ranking_source_incomplete"
        return 1, _report_lines(status="error", detail=detail)

    return 0, _report_lines(
        status="ok",
        detail="candidate_response_only",
        ranking_date=official_date.date().isoformat(),
        singles=singles,
        doubles=doubles,
    )


def _emit(lines: Sequence[str], output: TextIO) -> None:
    for line in lines:
        print(line, file=output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sanitized Matchstat ranking qualification probe")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    output: TextIO | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    environment = os.environ if environ is None else environ
    destination = sys.stdout if output is None else output
    exit_code, lines = probe(
        api_key=environment.get(API_KEY_ENV, ""),
        timeout_seconds=args.timeout_seconds,
    )
    _emit(lines, destination)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
