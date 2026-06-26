"""
update_career.py
Fetches recent match results from the ITF internal JSON API and appends
new events to data/career.json.

Called by .github/workflows/update_career.yml weekly on Sundays at 06:00 UTC.

Why Playwright:
  ITF is a JS SPA behind Imperva/Incapsula WAF. Plain requests() returns a
  bot-challenge page. Playwright runs a real Chromium instance which passes the
  Incapsula JS challenge, then intercepts the XHR response directly.

Player profile:
  https://www.itftennis.com/en/players/luka-bojicic-ono/800625103/bra/mt/s/activity/
  playerId = 800625103
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta

# ─── Config ───────────────────────────────────────────────────────────────────

PLAYER_ITF_ID   = "800625103"
CIRCUIT_CODE    = "MT"            # Men's Tour
MATCH_TYPE_CODE = "S"             # Singles
TAKE            = 50              # results per page
LOOKBACK_DAYS   = int(os.environ.get("LOOKBACK_DAYS", "30"))  # skip events older than N days; override via env for backfill
DATA_PATH       = "data/career.json"

ACTIVITY_URL = (
    "https://www.itftennis.com/en/players/luka-bojicic-ono/"
    f"{PLAYER_ITF_ID}/bra/mt/s/activity/"
)
API_URL = (
    "https://www.itftennis.com/tennis/api/PlayerApi/GetPlayerActivity"
    f"?circuitCode={CIRCUIT_CODE}&matchTypeCode={MATCH_TYPE_CODE}"
    f"&playerId={PLAYER_ITF_ID}&skip=0&surfaceCode=&take={TAKE}"
    f"&tourCategoryCode=&year="
)

# ─── Fetch via Playwright ──────────────────────────────────────────────────────

def fetch_activity() -> list[dict]:
    """
    Open the ITF activity page in a headless Chromium instance so Incapsula
    sets its cookies, then intercept the XHR call to GetPlayerActivity and
    return the parsed JSON payload.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    result: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # Intercept the API response
        api_response: list[dict] = []

        def handle_response(response):
            if "GetPlayerActivity" in response.url and response.status == 200:
                try:
                    data = response.json()
                    if isinstance(data, list):
                        api_response.extend(data)
                    elif isinstance(data, dict):
                        # API wraps results in a key; try common candidates
                        for key in ("events", "items", "results", "data", "matches", "activity", "playerActivity"):
                            if key in data and isinstance(data[key], list):
                                api_response.extend(data[key])
                                break
                        else:
                            # Fallback: dump raw keys so we can diagnose in logs
                            print(f"[warn] Unexpected API shape — top-level keys: {list(data.keys())}")
                except Exception as exc:
                    print(f"[warn] Failed to parse GetPlayerActivity response: {exc}")

        page.on("response", handle_response)

        try:
            print(f"Navigating to {ACTIVITY_URL} ...")
            page.goto(ACTIVITY_URL, timeout=60_000, wait_until="networkidle")
        except PWTimeout:
            print("Page load timed out — continuing with whatever was captured.")

        result = api_response

        browser.close()

    return result


# ─── Parse ────────────────────────────────────────────────────────────────────

# ITF activity records are TOURNAMENTS, each wrapping draws -> matches:
#   { tournamentName, location, dates: "18 May to 24 May 2026",
#     events: [ { drawType, matchType, matches: [ { opponents, roundGroup,
#                 resultCode, resultStatusCode, scores } ] } ] }
# We flatten singles matches into career.json events matching the existing
# shape: date, season, category, title, location, round, source_note.

_DATE_FORMATS = ("%d %b %Y", "%d %B %Y")


def parse_tournament_date(raw: str) -> date | None:
    """Take the START of an ITF date range like '18 May to 24 May 2026'."""
    s = (raw or "").strip()
    if not s:
        return None
    start, tail = s.split(" to ")[0].strip(), s.split(" to ")[-1].strip()
    year = re.search(r"\b(\d{4})\b", tail)
    if not re.search(r"\b\d{4}\b", start) and year:
        start = f"{start} {year.group(1)}"
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(start, fmt).date()
        except ValueError:
            continue
    return None


def round_token(draw_type: str, round_value: str) -> str | None:
    """Map (drawType, roundGroup.Value) to the career.json round vocabulary
    (Q-1R, Q-2R, Q-R16, 1R, R16, QF, SF, F)."""
    rv = (round_value or "").strip().lower()
    base: str | None = None
    ordinal = re.match(r"(\d+)\s*(?:st|nd|rd|th)?\s+round", rv)
    if ordinal:
        base = f"{ordinal.group(1)}R"
    elif "round of" in rv:
        n = re.search(r"round of\s+(\d+)", rv)
        base = f"R{n.group(1)}" if n else None
    elif "quarter" in rv:
        base = "QF"
    elif "semi" in rv:
        base = "SF"
    elif rv in ("final", "finals"):
        base = "F"
    if base is None:
        base = round_value or None
    if base and "qualifying" in (draw_type or "").lower():
        return f"Q-{base}"
    return base


def format_score(scores: list[dict], result_status: str | None) -> str:
    """Render set scores from the player's perspective: '6-2 3-6 8-10'."""
    sets = []
    for s in scores or []:
        a, b = s.get("scoreOne"), s.get("scoreTwo")
        if a is None or b is None:
            continue
        seg = f"{a}-{b}"
        ls = s.get("losingScore")
        if ls is not None:
            seg += f"({ls})"
        sets.append(seg)
    txt = " ".join(sets)
    if result_status == "RET":
        txt = f"{txt} (ret.)".strip()
    return txt


def opponent_name(opponents: list[dict]) -> str:
    """'Tsz Fu' + 'Wong' -> 'T. Wong' (career.json abbreviation style)."""
    if not opponents:
        return ""
    o = opponents[0]
    given = (o.get("givenName") or "").strip()
    family = (o.get("familyName") or "").strip()
    initial = f"{given[0]}." if given else ""
    return f"{initial} {family}".strip()


def parse_tournament(t: dict) -> list[dict]:
    """
    Convert one ITF activity tournament record into a list of career.json
    singles match events. Returns [] if outside the lookback window.
    All matches in a tournament inherit the tournament's start date
    (the activity feed carries no per-match dates).
    """
    if not isinstance(t, dict):
        print(f"[warn] Skipping non-dict record: {type(t).__name__}")
        return []

    t_date = parse_tournament_date(t.get("dates", ""))
    if t_date is None:
        print(f"[warn] Unparseable dates {t.get('dates')!r} for {t.get('tournamentName')!r}")
        return []

    if t_date < date.today() - timedelta(days=LOOKBACK_DAYS):
        return []

    tournament = t.get("tournamentName", "")
    location = t.get("location")

    events: list[dict] = []
    for draw in t.get("events", []) or []:
        if (draw.get("matchType") or "").lower() != "singles":
            continue
        draw_type = draw.get("drawType", "")
        for match in draw.get("matches", []) or []:
            result_code = match.get("resultCode", "")
            if result_code not in ("W", "L"):
                continue
            token = round_token(draw_type, (match.get("roundGroup") or {}).get("Value", ""))
            opp = opponent_name(match.get("opponents", []))

            parts = [tournament]
            if token:
                parts.append(token)
            if opp:
                parts.append(f"vs {opp}")
            title = " ".join(parts).strip()

            verb = "Won" if result_code == "W" else "Lost"
            score = format_score(match.get("scores", []), match.get("resultStatusCode"))
            source_note = f"{verb} {score}".strip() if score else f"{verb}; score unavailable"

            events.append({
                "date":        t_date.isoformat(),
                "season":      str(t_date.year),
                "category":    "tournament",
                "title":       title,
                "location":    location,
                "round":       token,
                "source_note": source_note,
            })
    return events


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Fetching activity for ITF player {PLAYER_ITF_ID}...")
    raw = fetch_activity()

    if not raw:
        print("No data received from ITF API — Incapsula may have blocked or no matches.")
        sys.exit(0)

    print(f"Received {len(raw)} raw records.")

    new_events = [ev for t in raw for ev in parse_tournament(t)]
    if not new_events:
        print(f"No matches within the last {LOOKBACK_DAYS} days.")
        sys.exit(0)

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    existing_events: list[dict] = data.get("career_events", data.get("events", []))

    existing_keys = {
        (e.get("date", ""), e.get("title", ""))
        for e in existing_events
    }

    added = 0
    for event in new_events:
        key = (event["date"], event["title"])
        if key not in existing_keys:
            existing_events.append(event)
            existing_keys.add(key)
            added += 1

    if added == 0:
        print("No new events to add — all already present.")
        sys.exit(0)

    # Some events (milestones, rankings) carry date: null — coerce to "" so the
    # sort doesn't compare None to str.
    existing_events.sort(key=lambda e: e.get("date") or "", reverse=True)

    # Support both "career_events" and "events" top-level keys
    if "career_events" in data:
        data["career_events"] = existing_events
    else:
        data["events"] = existing_events

    data["last_updated"] = date.today().isoformat()

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"career.json updated — {added} new event(s) added.")


if __name__ == "__main__":
    main()
