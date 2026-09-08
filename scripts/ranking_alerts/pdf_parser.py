"""Strict parser for the text extracted from an official ranking PDF.

The PDF layout is treated as a versioned contract.  It deliberately accepts a
small, explicit table shape rather than trying to recover values from arbitrary
nearby text: a changed report must stop collection for review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
import re
import unicodedata


class RankingReportParseError(ValueError):
    """Safe failure raised when a report cannot be parsed unambiguously."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PdfExtractionError(ValueError):
    """Safe failure raised when bytes are not a readable, text-based PDF."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ParsedRankingReport:
    discipline: str
    ranking_date: str
    player_name: str
    rank: int
    points: int


_SUPPORTED_DISCIPLINES = frozenset({"singles", "doubles"})
_TABLE_HEADER = re.compile(r"^\s*rank\s+player\s+points\s*$", re.IGNORECASE)
_DATE_LABEL = re.compile(
    r"\b(?:ranking\s+date|rankings?\s+as\s+of|as\s+of)\s*[:\-]?\s*"
    r"(?P<value>\d{4}[-/.]\d{2}[-/.]\d{2}|"
    r"(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}))\b",
    re.IGNORECASE,
)
_DISCIPLINE_LABEL = r"(?:atp\s+)?{discipline}\s+rankings?\b"
_ROW = re.compile(
    r"^\s*(?P<rank>\S+)\s+(?P<player>.+?)\s+"
    r"(?P<points>\d[\d, \u00a0\u202f]*)\s*$"
)
_RANK = re.compile(r"(?:[1-9]\d{0,2}(?:[,\u00a0\u202f]\d{3})*|[1-9]\d*)T?", re.IGNORECASE)
_NUMBER = re.compile(r"(?:0|[1-9]\d{0,2}(?:[ ,\u00a0\u202f]\d{3})*|[1-9]\d*)")


def _comparison_value(value: str) -> str:
    """Normalize benign PDF text differences while retaining exact identity."""

    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(unicodedata.normalize("NFKC", without_marks).casefold().split())


def _canonical_date(value: str) -> str:
    candidate = value.strip()
    if re.fullmatch(r"\d{4}[-/.]\d{2}[-/.]\d{2}", candidate):
        candidate = re.sub(r"[/.]", "-", candidate)
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            raise RankingReportParseError("ranking_report_date_invalid") from None

    for pattern in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.strptime(candidate, pattern).date().isoformat()
        except ValueError:
            continue
    raise RankingReportParseError("ranking_report_date_invalid")


def _parse_number(value: str, *, field: str) -> int:
    cleaned = value.replace("\u00a0", " ").replace("\u202f", " ")
    if not _NUMBER.fullmatch(cleaned):
        raise RankingReportParseError(f"ranking_report_{field}_invalid")
    return int(re.sub(r"[ ,]", "", cleaned))


def _ranking_date(text: str) -> str:
    values = {_canonical_date(match.group("value")) for match in _DATE_LABEL.finditer(text)}
    if not values:
        raise RankingReportParseError("ranking_report_date_missing")
    if len(values) != 1:
        raise RankingReportParseError("ranking_report_date_ambiguous")
    return values.pop()


def _validate_report_layout(lines: list[str], discipline: str) -> int:
    label = re.compile(_DISCIPLINE_LABEL.format(discipline=re.escape(discipline)), re.IGNORECASE)
    if not any(label.search(line) for line in lines):
        raise RankingReportParseError("ranking_report_layout_changed")

    headers = [index for index, line in enumerate(lines) if _TABLE_HEADER.fullmatch(line)]
    if len(headers) != 1:
        raise RankingReportParseError("ranking_report_layout_changed")
    return headers[0]


def parse_ranking_report(text: str, discipline: str, expected_player: str) -> ParsedRankingReport:
    """Parse one exact player row from a text-based ranking report.

    The accepted table is ``Rank Player Points``.  Rank may have a trailing
    ``T`` for a tie; points may use comma, space, non-breaking-space, or thin
    non-breaking-space thousands separators.  Any other row shape is rejected
    instead of guessed.
    """

    normalized_discipline = discipline.strip().casefold() if isinstance(discipline, str) else ""
    if normalized_discipline not in _SUPPORTED_DISCIPLINES:
        raise RankingReportParseError("ranking_report_discipline_invalid")
    if not isinstance(text, str) or not text.strip():
        raise RankingReportParseError("ranking_report_text_invalid")
    if not isinstance(expected_player, str) or not _comparison_value(expected_player):
        raise RankingReportParseError("ranking_report_player_invalid")

    lines = text.splitlines()
    header_index = _validate_report_layout(lines, normalized_discipline)
    ranking_date = _ranking_date(text)
    expected = _comparison_value(expected_player)
    matches: list[tuple[str, str, str]] = []
    player_mentioned = False

    for line in lines[header_index + 1 :]:
        row = _ROW.fullmatch(line)
        if row is not None and _comparison_value(row.group("player")) == expected:
            matches.append((row.group("rank"), row.group("player"), row.group("points")))
        normalized_line = _comparison_value(line)
        if re.search(rf"(?:^|\s){re.escape(expected)}(?=$|\s+\d)", normalized_line):
            player_mentioned = True

    if not matches:
        if player_mentioned:
            raise RankingReportParseError("ranking_report_row_invalid")
        raise RankingReportParseError("ranking_report_player_missing")
    if len(matches) != 1:
        raise RankingReportParseError("ranking_report_player_ambiguous")

    rank_text, player_name, points_text = matches[0]
    if not _RANK.fullmatch(rank_text):
        raise RankingReportParseError("ranking_report_rank_invalid")
    rank = _parse_number(rank_text[:-1] if rank_text.casefold().endswith("t") else rank_text, field="rank")
    if rank <= 0:
        raise RankingReportParseError("ranking_report_rank_invalid")
    points = _parse_number(points_text, field="points")
    return ParsedRankingReport(
        discipline=normalized_discipline,
        ranking_date=ranking_date,
        player_name=player_name.strip(),
        rank=rank,
        points=points,
    )


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from structurally valid, unencrypted PDF bytes only.

    Parsing of the report itself remains separate in :func:`parse_ranking_report`
    so callers can validate downloaded bytes before trusting their text.
    """

    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
        raise PdfExtractionError("pdf_invalid")
    if not pdf_bytes.rstrip().endswith(b"%%EOF"):
        raise PdfExtractionError("pdf_invalid")
    try:
        from pypdf import PdfReader
    except ImportError:
        raise PdfExtractionError("pdf_extraction_unavailable") from None

    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=True)
        if reader.is_encrypted or not reader.pages:
            raise PdfExtractionError("pdf_invalid")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except PdfExtractionError:
        raise
    except Exception:
        raise PdfExtractionError("pdf_invalid") from None
    if not text.strip():
        raise PdfExtractionError("pdf_text_missing")
    return text
