#!/usr/bin/env python3
"""Read-only, redacted qualification probe for ATP ranking PDFs.

This tool intentionally has no storage, workflow, or notification imports.
It can report a candidate observation, but never approves a production source.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from ranking_alerts.atp_pdf_source import AtpPdfRankingSource
from ranking_alerts.source import RankingSourceError, RawRankingObservation


def _lines(*, status: str, detail: str, observation: RawRankingObservation | None = None) -> tuple[str, ...]:
    lines = ("probe=atp-pdf", f"status={status}", f"detail={detail}")
    if observation is not None:
        lines += (
            "evidence_exact_name_match=true",
            "evidence_singles_present=true",
            "evidence_doubles_individual=true",
            "evidence_same_ranking_date=true",
        )
    return lines + (
        "gate_identity=pending_manual_review",
        "gate_singles_individual=pending_manual_review",
        "gate_doubles_individual=pending_manual_review",
        "gate_official_ranking_date=pending_manual_review",
        "gate_coverage_beyond_2000=pending_manual_review",
        "gate_two_publications=pending_manual_review",
    )


def probe(source: AtpPdfRankingSource | None = None) -> tuple[int, tuple[str, ...]]:
    """Fetch and validate only; neither persist nor notify under any outcome."""

    candidate = source if source is not None else AtpPdfRankingSource()
    try:
        observation = candidate.fetch()
    except RankingSourceError as exc:
        return 1, _lines(status="error", detail=exc.code) + ("decision=no-go",)
    except Exception:
        return 1, _lines(status="error", detail="ranking_source_incomplete") + ("decision=no-go",)
    return 0, _lines(status="ok", detail="candidate_observation_valid", observation=observation) + (
        "decision=pending_manual_review",
    )


def main(argv: Sequence[str] | None = None, *, output: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sanitized ATP PDF qualification probe")
    parser.add_argument("--timeout-seconds", type=float, default=None)
    args = parser.parse_args(argv)
    source = AtpPdfRankingSource(**({"timeout_seconds": args.timeout_seconds} if args.timeout_seconds else {}))
    exit_code, lines = probe(source)
    for line in lines:
        print(line, file=sys.stdout if output is None else output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
