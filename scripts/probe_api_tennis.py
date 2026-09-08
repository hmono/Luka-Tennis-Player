#!/usr/bin/env python3
"""Run a non-persistent, redacted qualification probe for API-Tennis.

API-Tennis remains a candidate source. A successful response leaves the spike
pending manual review; this tool cannot approve a provider by itself.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TextIO


API_KEY_ENV = "API_TENNIS_API_KEY"
DEFAULT_ENDPOINT = "https://api.api-tennis.com/tennis/"
DEFAULT_METHOD = "get_standings"
DEFAULT_EVENT_TYPE = "ATP"
DEFAULT_PLAYER_NAME = "Luka Bojicic Ono"
MAX_RESPONSE_BYTES = 512 * 1024


def _http_error_code(status: int) -> str:
    if status == 401:
        return "ranking_source_authentication"
    if status == 403:
        return "ranking_source_blocked"
    if status == 429:
        return "ranking_source_rate_limited"
    return "ranking_source_incomplete"


def _standing_rows(payload: Any) -> tuple[Mapping[str, Any], ...] | None:
    """Return only structurally valid rows from the documented response shape."""

    if not isinstance(payload, Mapping):
        return None
    success = payload.get("success")
    result = payload.get("result")
    if isinstance(success, bool) or success != 1 or not isinstance(result, list):
        return None
    if any(not isinstance(row, Mapping) or not isinstance(row.get("player"), str) for row in result):
        return None
    return tuple(result)


def _contains_exact_player_name(rows: Sequence[Mapping[str, Any]], player_name: str) -> bool:
    """Find the candidate only in documented standing-row player fields."""

    expected = " ".join(player_name.casefold().split())
    return any(" ".join(row["player"].casefold().split()) == expected for row in rows)


def _report_lines(
    *,
    status: str,
    detail: str,
    response_within_limit: bool | None = None,
    candidate_name_match: bool | None = None,
) -> tuple[str, ...]:
    lines = ("probe=api-tennis", f"status={status}", f"detail={detail}")
    if response_within_limit is not None:
        lines += (f"evidence_response_within_limit={str(response_within_limit).lower()}",)
    if candidate_name_match is not None:
        lines += (f"evidence_candidate_name_match={str(candidate_name_match).lower()}",)
    return lines + (
        "gate_identity=pending_manual_review",
        "gate_singles_individual=pending_manual_review",
        "gate_doubles_individual=pending_manual_review",
        "gate_official_ranking_date=pending_manual_review",
        "gate_coverage_beyond_2000=pending_manual_review",
        "gate_two_publications=pending_manual_review",
    )


def _with_decision(lines: tuple[str, ...], decision: str) -> tuple[str, ...]:
    if decision not in {"no-go", "pending_manual_review"}:
        raise ValueError("invalid_probe_decision")
    return lines + (f"decision={decision}",)


def _no_go(*, status: str, detail: str, **evidence: bool) -> tuple[int, tuple[str, ...]]:
    return 1, _with_decision(
        _report_lines(status=status, detail=detail, **evidence),
        "no-go",
    )


def probe(
    *,
    api_key: str,
    endpoint: str = DEFAULT_ENDPOINT,
    player_name: str = DEFAULT_PLAYER_NAME,
    timeout_seconds: float = 20.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> tuple[int, tuple[str, ...]]:
    """Perform one request and return a redacted report; never writes a file."""

    if not api_key:
        exit_code, lines = _no_go(status="error", detail="ranking_source_authentication")
        return 2, lines
    if endpoint != DEFAULT_ENDPOINT:
        exit_code, lines = _no_go(status="error", detail="ranking_source_incomplete")
        return 2, lines

    query = urllib.parse.urlencode(
        {"method": DEFAULT_METHOD, "event_type": DEFAULT_EVENT_TYPE, "APIkey": api_key}
    )
    request = urllib.request.Request(f"{endpoint}?{query}", method="GET")
    try:
        with opener(request, timeout=timeout_seconds) as response:
            status = int(response.getcode())
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return _no_go(status="error", detail=_http_error_code(exc.code))
    except (TimeoutError, socket.timeout):
        return _no_go(status="error", detail="ranking_source_timeout")
    except (urllib.error.URLError, OSError):
        return _no_go(status="error", detail="ranking_source_incomplete")

    if status != 200:
        return _no_go(status="error", detail=_http_error_code(status))
    if len(body) > MAX_RESPONSE_BYTES:
        return _no_go(
            status="error",
            detail="ranking_source_coverage_truncated",
            response_within_limit=False,
        )
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _no_go(
            status="error",
            detail="ranking_source_schema_changed",
            response_within_limit=True,
        )

    rows = _standing_rows(payload)
    if rows is None:
        return _no_go(
            status="error",
            detail="ranking_source_schema_changed",
            response_within_limit=True,
        )

    candidate_found = _contains_exact_player_name(rows, player_name)
    if not candidate_found:
        return _no_go(
            status="error",
            detail="ranking_source_incomplete",
            response_within_limit=True,
            candidate_name_match=False,
        )
    return 0, _with_decision(
        _report_lines(
            status="ok",
            detail="candidate_name_found",
            response_within_limit=True,
            candidate_name_match=True,
        ),
        "pending_manual_review",
    )


def _emit(lines: Sequence[str], output: TextIO) -> None:
    for line in lines:
        print(line, file=output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sanitized API-Tennis qualification probe")
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
