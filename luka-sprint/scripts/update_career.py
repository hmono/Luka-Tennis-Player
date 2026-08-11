"""
update_career.py
Scrapes recent match results from the ITF website and appends new events
to data/career.json.

Called by .github/workflows/update_career.yml weekly on Sundays at 06:00 UTC.

SETUP REQUIRED:
  Set PLAYER_ITF_ID below (find it in the URL of the player's ITF profile page).
  e.g. https://www.itftennis.com/en/players/100123456/luka-ojcic-ono/
  → PLAYER_ITF_ID = "100123456"
"""

import json
import re
from datetime import datetime, date, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ─── Config ───────────────────────────────────────────────────────────────────

PLAYER_ITF_ID = "100610195"          # TODO: confirm from ITF profile URL
BASE_URL      = "https://www.itftennis.com"
RESULTS_URL   = f"{BASE_URL}/en/players/{PLAYER_ITF_ID}/results/"
DATA_PATH     = "data/career.json"
LOOKBACK_DAYS = 14                   # fetch matches in the last N days

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; LukaTennisBot/1.0; "
        "+https://github.com/hmono/Luka-Tennis-Player)"
    )
}

# ─── Scraping ─────────────────────────────────────────────────────────────────

def fetch_html(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def current_season() -> str:
    return str(date.today().year)


def parse_match_rows(soup: BeautifulSoup) -> list[dict]:
    """
    Parse match result rows from the ITF player results page.
    Returns a list of raw row dicts with keys matching career.json event shape.
    """
    events = []
    cutoff = date.today() - timedelta(days=LOOKBACK_DAYS)

    # ITF results page: rows are inside a table or a results list.
    # Selector targets the standard results table structure as of 2026.
    rows = soup.select("table.results-table tbody tr, .results-list .result-row")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        date_text       = cells[0].get_text(strip=True)
        tournament_text = cells[1].get_text(strip=True)
        round_text      = cells[2].get_text(strip=True)
        opponent_text   = cells[3].get_text(strip=True)
        result_text     = cells[4].get_text(strip=True)

        # Parse date — ITF uses dd MMM YYYY format
        try:
            match_date = datetime.strptime(date_text, "%d %b %Y").date()
        except ValueError:
            continue

        if match_date < cutoff:
            continue

        result_upper = result_text.upper()
        won  = result_upper.startswith("W")
        lost = result_upper.startswith("L")

        title = f"{tournament_text} {round_text}"
        if won:
            title += f" Won vs {opponent_text}"
        elif lost:
            title += f" Lost to {opponent_text}"

        events.append({
            "title":       title,
            "source_note": f"ITF result: {result_text}",
            "season":      str(match_date.year),
            "date":        match_date.isoformat(),
        })

    return events


def infer_level(tournament_name: str) -> str:
    name = tournament_name.upper()
    if "M15" in name:
        return "M15"
    if "M25" in name:
        return "M25"
    if "CHALLENGER" in name:
        return "Challenger"
    if "ATP" in name:
        return "ATP"
    return "M25"   # default for Futures

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Fetching results for ITF player {PLAYER_ITF_ID}...")
    soup = fetch_html(RESULTS_URL)

    new_events = parse_match_rows(soup)
    if not new_events:
        print("No new match rows found — page structure may have changed or no recent matches.")
        return

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    existing_events: list[dict] = data.get("events", [])

    # Deduplicate by (date, title) to avoid re-adding the same match.
    existing_keys = {
        (e.get("date", ""), e.get("title", ""))
        for e in existing_events
    }

    added = 0
    for event in new_events:
        key = (event.get("date", ""), event.get("title", ""))
        if key not in existing_keys:
            existing_events.append(event)
            existing_keys.add(key)
            added += 1

    if added == 0:
        print("No new events to add.")
        return

    # Keep sorted descending by date.
    existing_events.sort(key=lambda e: e.get("date", ""), reverse=True)
    data["events"]       = existing_events
    data["last_updated"] = date.today().isoformat()

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"career.json updated — {added} new event(s) added.")


if __name__ == "__main__":
    main()
