"""
update_physiology.py
Fetches the latest WHOOP recovery data and appends a log entry to data/physiology.json.

Called by .github/workflows/update_physiology.yml daily at 07:00 UTC.
Required env vars: WHOOP_ACCESS_TOKEN, WHOOP_REFRESH_TOKEN, WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

# ─── Constants ────────────────────────────────────────────────────────────────

TOKEN_URL  = "https://api.prod.whoop.com/oauth/oauth2/token"
API_BASE   = "https://api.prod.whoop.com/developer/v1"
DATA_PATH  = "data/physiology.json"

# ─── Auth ─────────────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    resp = requests.post(TOKEN_URL, data={
        "grant_type":    "refresh_token",
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }, timeout=15)
    resp.raise_for_status()
    # NOTE: the new refresh_token in resp.json() cannot be auto-persisted to
    # GitHub Secrets. Rotate secrets manually every ~30 days or implement a
    # secrets-update step via the GitHub API if tokens expire.
    return resp.json()["access_token"]


def _get(token: str, path: str, params: dict | None = None) -> dict:
    resp = requests.get(f"{API_BASE}{path}", headers=_headers(token),
                        params=params or {}, timeout=15)
    resp.raise_for_status()
    return resp.json()

# ─── WHOOP data fetchers ──────────────────────────────────────────────────────

def latest_recovery(token: str) -> dict | None:
    data = _get(token, "/recovery", {"limit": 1})
    records = data.get("records", [])
    return records[0] if records else None


def latest_cycle(token: str) -> dict | None:
    data = _get(token, "/cycle", {"limit": 1})
    records = data.get("records", [])
    return records[0] if records else None


def latest_sleep(token: str) -> dict | None:
    data = _get(token, "/sleep", {"limit": 1})
    records = data.get("records", [])
    return records[0] if records else None

# ─── Helpers ──────────────────────────────────────────────────────────────────

def hrv_status(recovery_pct: float) -> str:
    if recovery_pct >= 80:
        return "above_baseline"
    if recovery_pct >= 50:
        return "stable"
    if recovery_pct >= 33:
        return "declining"
    return "critical"


def classification(recovery_pct: float) -> str:
    if recovery_pct >= 67:
        return "High readiness"
    if recovery_pct >= 34:
        return "Moderate readiness"
    if recovery_pct > 0:
        return "Low readiness"
    return "Rest"

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    client_id     = os.environ["WHOOP_CLIENT_ID"]
    client_secret = os.environ["WHOOP_CLIENT_SECRET"]
    access_token  = os.environ["WHOOP_ACCESS_TOKEN"]
    refresh_token = os.environ["WHOOP_REFRESH_TOKEN"]

    # Proactively refresh — daily workflow may run with a stale token.
    try:
        access_token = refresh_access_token(client_id, client_secret, refresh_token)
        print("Token refreshed.")
    except requests.HTTPError as e:
        print(f"Token refresh failed ({e}); trying stored access token.")

    recovery = latest_recovery(access_token)
    if not recovery:
        print("No recovery record available — skipping update.")
        sys.exit(0)

    cycle = latest_cycle(access_token)
    sleep = latest_sleep(access_token)

    score    = recovery.get("score", {})
    rec_pct  = round(score.get("recovery_score", 0))
    hrv_ms   = round(score.get("hrv_rmssd_milli", 0))
    rhr_bpm  = round(score.get("resting_heart_rate", 0))
    strain   = round(cycle["score"]["strain"], 1) if cycle and cycle.get("score") else None
    sleep_pct = round(sleep["score"]["sleep_performance_percentage"]) \
                if sleep and sleep.get("score") else None

    entry = {
        "date":           datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "recovery_pct":   rec_pct,
        "hrv_ms":         hrv_ms,
        "resting_hr_bpm": rhr_bpm,
        "strain":         strain,
        "sleep_pct":      sleep_pct,
        "classification": classification(rec_pct),
        "hrv_status":     hrv_status(rec_pct),
    }

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    log = data.get("log", [])

    # Upsert: replace existing entry for the same date.
    idx = next((i for i, e in enumerate(log) if e.get("date") == entry["date"]), None)
    if idx is not None:
        log[idx] = entry
        print(f"Updated existing entry for {entry['date']}.")
    else:
        log.append(entry)
        print(f"Appended new entry for {entry['date']}.")

    data["log"]          = sorted(log, key=lambda e: e.get("date", ""))
    data["last_updated"] = entry["date"]

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"physiology.json updated — recovery {rec_pct}% | strain {strain} | sleep {sleep_pct}%")


if __name__ == "__main__":
    main()
