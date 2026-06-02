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
import sys
from datetime import date, datetime, timedelta

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─── Config ───────────────────────────────────────────────────────────────────

PLAYER_ITF_ID   = "800625103"
CIRCUIT_CODE    = "MT"            # Men's Tour
MATCH_TYPE_CODE = "S"             # Singles
TAKE            = 50              # results per page
LOOKBACK_DAYS   = 30              # skip events older than N days
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
                        for key in ("items", "results", "data", "matches", "activity", "playerActivity"):
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

def parse_match(m: dict) -> dict | None:
    """
    Convert one ITF GetPlayerActivity record to a career.json event shape.
    Returns None if the match is outside the lookback window.
    """
    if not isinstance(m, dict):
        print(f"[warn] Skipping non-dict record: {type(m).__name__} = {m!r}")
        return None

    cutoff = date.today() - timedelta(days=LOOKBACK_DAYS)

    # Dates come as "YYYY-MM-DDTHH:MM:SS" or similar ISO strings
    raw_dates: list[str] = m.get("dates", []) or []
    match_date: date | None = None
    for raw in raw_dates:
        try:
            match_date = datetime.fromisoformat(raw[:10]).date()
            break
        except ValueError:
            continue

    if match_date is None or match_date < cutoff:
        return None

    tournament   = m.get("tournamentName", "")
    round_label  = (m.get("roundGroup", {}) or {}).get("label", "")
    result_code  = m.get("resultCode", "")      # "W" or "L"
    opp          = m.get("opponents", [{}])
    opp_name     = ""
    if opp:
        o = opp[0]
        opp_name = f"{o.get('givenName','')} {o.get('familyName','')}".strip()

    won  = result_code == "W"
    lost = result_code == "L"

    title = f"{tournament} {round_label}".strip()
    if won and opp_name:
        title += f" Won vs {opp_name}"
    elif lost and opp_name:
        title += f" Lost to {opp_name}"

    tour_code = m.get("tourCode", "ITF")

    return {
        "title":       title,
        "source_note": f"ITF result: {'W' if won else 'L'} — {tournament}",
        "season":      str(match_date.year),
        "date":        match_date.isoformat(),
        "category":    "tournament",
        "round":       round_label or None,
        "location":    m.get("location"),
        "tour":        tour_code,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Fetching activity for ITF player {PLAYER_ITF_ID}...")
    raw = fetch_activity()

    if not raw:
        print("No data received from ITF API — Incapsula may have blocked or no matches.")
        sys.exit(0)

    print(f"Received {len(raw)} raw records.")

    new_events = [e for m in raw if (e := parse_match(m)) is not None]
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

    existing_events.sort(key=lambda e: e.get("date", ""), reverse=True)

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
