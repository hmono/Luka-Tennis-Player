"""Calendar-free polling, weekly status periods, and an independent watchdog.

The watchdog lives outside Actions. No workflow enable endpoint is used. Network
writes require initial release, and dispatch is bounded per expected slot.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import fcntl
import hashlib
import json
import os
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping
from zoneinfo import ZoneInfo

UTC = timezone.utc
SAO_PAULO = ZoneInfo("America/Sao_Paulo")
POLL_HOURS = (12, 18)
POLL_MINUTE = 17
GRACE = timedelta(minutes=90)
MAX_DURATION = timedelta(minutes=20)
RECOVERY_WINDOW = timedelta(hours=6)
RECOVERY_BACKOFF = timedelta(minutes=30)
MAX_RECOVERIES = 2


def aware(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("timezone_required")
    return now.astimezone(UTC)


def iso(now: datetime) -> str:
    return aware(now).isoformat().replace("+00:00", "Z")


def parse(value: str) -> datetime:
    return aware(datetime.fromisoformat(value.replace("Z", "+00:00")))


def poll_slots(now: datetime, days: int = 2) -> list[datetime]:
    """Every day, twice daily, including weekends; no ATP calendar input."""
    now = aware(now)
    slots = [
        (now - timedelta(days=offset)).replace(hour=hour, minute=POLL_MINUTE, second=0, microsecond=0)
        for offset in range(days + 1) for hour in POLL_HOURS
    ]
    for offset in range(days + 1):
        day = now - timedelta(days=offset)
        if day.weekday() == 0:
            slots.append(day.replace(hour=12, minute=0, second=0, microsecond=0))
    return sorted(set(slot for slot in slots if slot <= now))


def ranking_poll_slots(now: datetime) -> list[datetime]:
    """MVP schedule: weekdays at 12:00 UTC, including the prior Friday."""
    now = aware(now)
    slots = [(now - timedelta(days=offset)).replace(hour=12, minute=0, second=0, microsecond=0)
             for offset in range(8)]
    return sorted(slot for slot in slots if slot.weekday() < 5 and slot <= now)


def weekly_period(now: datetime) -> str:
    """ID of the latest Monday 09:00 Sao Paulo, independent of editions.

    A cycle before this week's instant belongs to last week's period. Missed
    cycles catch up once, using this ID as the delivery ledger dedup key.
    """
    local = aware(now).astimezone(SAO_PAULO)
    monday = (local - timedelta(days=local.weekday())).replace(hour=9, minute=0, second=0, microsecond=0)
    if local < monday:
        monday -= timedelta(days=7)
    return monday.date().isoformat()


@dataclass(frozen=True)
class SchedulerIncident:
    event_id: str
    code: str
    slot: str
    message: str
    recoverable: bool = False


def assess_runs(now: datetime, runs: list[Mapping], *, grace: timedelta = GRACE) -> list[SchedulerIncident]:
    """Assess the latest due poll; manual recovery can satisfy its slot.

    Only main runs with schedule/dispatch events qualify. Success proves a
    cycle ran, never that source data changed or a message reached a device.
    """
    now = aware(now)
    due = [slot for slot in poll_slots(now) if slot + grace <= now]
    if not due:
        return []
    slot = due[-1]
    # Runs for the following poll must not mask an earlier missing slot.
    next_slot = next((candidate for candidate in poll_slots(slot + timedelta(days=1)) if candidate > slot), slot + timedelta(days=1))
    eligible = []
    for run in runs:
        if run.get("head_branch") != "main" or run.get("event") not in {"schedule", "workflow_dispatch"}:
            continue
        if run.get("event") == "workflow_dispatch" and "collect-and-deliver" not in run.get("display_title", ""):
            continue
        created = parse(run["created_at"])
        if slot <= created < next_slot:
            eligible.append(run)
    sid = iso(slot)
    incidents = []
    def add(code: str, message: str, recoverable: bool = False, suffix: str = "") -> None:
        incidents.append(SchedulerIncident(f"scheduler:{code}:{sid}{suffix}", code, sid, message, recoverable))
    if not eligible:
        add("MISSED_RUN", f"No main ranking cycle observed for {sid} after 90-minute grace; source status unknown.", True)
        return incidents
    # A successful or still active newer run supersedes an earlier failure for recovery.
    latest = max(eligible, key=lambda run: (run["created_at"], int(run.get("id", 0))))
    started = parse(latest.get("run_started_at") or latest["created_at"])
    if started - slot > timedelta(minutes=60):
        add("SCHEDULER_DELAY", f"Ranking cycle for {sid} started more than 60 minutes late.")
    if latest.get("status") != "completed":
        if now - started > MAX_DURATION:
            add("RUN_DURATION", f"Ranking cycle for {sid} has remained queued/running over 20 minutes; source status unknown.")
    else:
        completed = parse(latest.get("updated_at") or iso(now))
        if completed - started > MAX_DURATION:
            add("RUN_DURATION", f"Ranking cycle for {sid} exceeded 20 minutes.")
        if latest.get("conclusion") != "success":
            add("RUN_FAILURE", f"Ranking cycle for {sid} failed ({latest.get('conclusion') or 'unknown'}); source status unknown.", True)
    return incidents


class WatchdogStore:
    """External host disk, independent of Git/Actions runner availability."""
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory = directory
        self.path = directory / "watchdog.sqlite3"
        self.connection = sqlite3.connect(self.path, timeout=30)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, message TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, last_attempt TEXT);
            CREATE TABLE IF NOT EXISTS recoveries (slot TEXT NOT NULL, attempt INTEGER NOT NULL, requested_at TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(slot, attempt));
            CREATE TABLE IF NOT EXISTS health (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        self.connection.commit()

    def close(self):
        self.connection.close()

    @contextlib.contextmanager
    def locked(self):
        with (self.directory / "watchdog.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def enqueue(self, event_id: str, message: str):
        self.connection.execute("INSERT OR IGNORE INTO alerts(id,message,status) VALUES(?,?,'pending')", (event_id, message))
        self.connection.commit()

    def flush(self, sender: Callable[[str, str], bool], now: datetime) -> int:
        sent = 0
        rows = self.connection.execute("SELECT id,message,last_attempt FROM alerts WHERE status='pending' ORDER BY id LIMIT 8").fetchall()
        for event_id, message, last in rows:
            if last and aware(now) - parse(last) < timedelta(minutes=10):
                continue
            # Commit intent before the call. A crash may replay: receiver MUST
            # deduplicate event_id/Idempotency-Key. HTTP acceptance is not delivery.
            self.connection.execute("UPDATE alerts SET attempts=attempts+1,last_attempt=? WHERE id=?", (iso(now), event_id))
            self.connection.commit()
            try:
                accepted = sender(event_id, message)
            except Exception:
                accepted = False
            if accepted:
                self.connection.execute("UPDATE alerts SET status='accepted' WHERE id=?", (event_id,))
                self.connection.commit()
                sent += 1
        return sent

    def reserve_recovery(self, slot: str, now: datetime) -> int | None:
        if aware(now) - parse(slot) > RECOVERY_WINDOW:
            return None
        rows = self.connection.execute("SELECT attempt,requested_at FROM recoveries WHERE slot=? ORDER BY attempt", (slot,)).fetchall()
        if len(rows) >= MAX_RECOVERIES or (rows and aware(now) - parse(rows[-1][1]) < RECOVERY_BACKOFF):
            return None
        attempt = len(rows) + 1
        # Durable reservation bounds uncertain HTTP requests as well as accepted ones.
        self.connection.execute("INSERT INTO recoveries VALUES(?,?,?,'reserved')", (slot, attempt, iso(now)))
        self.connection.commit()
        return attempt

    def recovery_result(self, slot: str, attempt: int, result: str):
        self.connection.execute("UPDATE recoveries SET result=? WHERE slot=? AND attempt=?", (result, slot, attempt))
        self.connection.commit()


def _request(url: str, *, token: str = "", payload: dict | None = None, event_id: str = ""):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ranking-independent-watchdog", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if event_id:
        headers["Idempotency-Key"] = hashlib.sha256(event_id.encode()).hexdigest()
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers=headers)
    # Bound response bytes; never persist or print URLs, response bodies or tokens.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(request, timeout=15) as response:
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError("response_too_large")
        return json.loads(body) if body else {}


def webhook_sender(event_id: str, message: str) -> bool:
    url = os.environ.get("ATP_OPS_WEBHOOK_URL", "")
    if not url or urllib.parse.urlparse(url).scheme != "https":
        return False
    try:
        result = _request(url, token=os.environ.get("ATP_OPS_WEBHOOK_TOKEN", ""), payload={"event_id": event_id, "message": message, "kind": "ranking_operational"}, event_id=event_id)
        return isinstance(result, dict) and result.get("accepted") is True
    except Exception:
        return False


def send_operational_alert(event_id: str, message: str) -> bool:
    """Optional independent ops callback for the production ranking runtime.

    Unconfigured means no send and False. The Git delivery ledger remains the
    source of retryable ranking events; external watchdog keeps its own disk.
    """
    if os.environ.get("ATP_RANKING_DELIVERY_ENABLED") != "true" or not os.environ.get("ATP_OPS_WEBHOOK_URL"):
        return False
    directory = Path(os.environ.get("ATP_WATCHDOG_STATE_DIR", "/var/lib/atp-ranking-watchdog"))
    store = WatchdogStore(directory)
    try:
        with store.locked():
            store.enqueue(event_id, message)
            store.flush(webhook_sender, datetime.now(UTC))
            return store.connection.execute("SELECT status FROM alerts WHERE id=?", (event_id,)).fetchone()[0] == "accepted"
    finally:
        store.close()


class GitHubActionsClient:
    def __init__(self, repo: str, token: str):
        if len(repo.split("/")) != 2 or any(not part or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for c in part) for part in repo.split("/")):
            raise ValueError("invalid_repository")
        self.base = f"https://api.github.com/repos/{repo}/actions/workflows/update_rankings.yml"
        self.token = token
        self.token_expires = None

    def authentication_token(self):
        app_id = os.environ.get("ATP_WATCHDOG_APP_ID", "")
        installation_id = os.environ.get("ATP_WATCHDOG_APP_INSTALLATION_ID", "")
        private_key = os.environ.get("ATP_WATCHDOG_APP_PRIVATE_KEY_PATH", "")
        if not any((app_id, installation_id, private_key)):
            return self.token
        if not (app_id.isdigit() and installation_id.isdigit() and private_key):
            raise ValueError("app_credentials_incomplete")
        now = datetime.now(UTC)
        if self.token_expires and now + timedelta(minutes=1) < self.token_expires:
            return self.token
        def encode(value):
            return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
        instant = int(time.time())
        header = encode(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
        claims = encode(json.dumps({"iat": instant - 60, "exp": instant + 540, "iss": app_id}, separators=(",", ":")).encode())
        signing_input = f"{header}.{claims}"
        signed = subprocess.run(["openssl", "dgst", "-sha256", "-sign", private_key], input=signing_input.encode(), capture_output=True, check=True, timeout=10)
        jwt = signing_input + "." + encode(signed.stdout)
        grant = _request(f"https://api.github.com/app/installations/{installation_id}/access_tokens", token=jwt, payload={})
        self.token, self.token_expires = grant["token"], parse(grant["expires_at"])
        return self.token

    def inspect(self) -> tuple[str, list[Mapping]]:
        metadata = _request(self.base, token=self.authentication_token())
        if metadata["state"] != "active":
            return metadata["state"], []
        runs = []
        # Paginate: a burst of manual dry-runs cannot hide the main scheduled run.
        for page in range(1, 6):
            batch = _request(f"{self.base}/runs?branch=main&per_page=100&page={page}", token=self.authentication_token())["workflow_runs"]
            runs.extend(batch)
            if len(batch) < 100:
                break
        else:
            raise ValueError("run_metadata_truncated")
        return metadata["state"], runs

    def dispatch(self):
        _request(self.base + "/dispatches", token=self.authentication_token(), payload={"ref": "main", "inputs": {"mode": "collect-and-deliver"}})


def watchdog_cycle(*, now: datetime, client, store: WatchdogStore, sender: Callable[[str, str], bool], released: bool, recovery_enabled: bool) -> dict:
    """Read-only unless released; never enables disabled workflows."""
    now = aware(now)
    incidents = []
    state = "unknown"
    try:
        state, runs = client.inspect()
        if state != "active":
            incidents = [SchedulerIncident(f"scheduler:WORKFLOW_DISABLED:{state}", "WORKFLOW_DISABLED", "", "Ranking workflow is disabled; source status unknown. Initial release is required.")]
        else:
            incidents = assess_runs(now, runs)
    except Exception:
        # One alert per six-hour outage epoch, independent of sports provider.
        epoch = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)
        incidents = [SchedulerIncident(f"scheduler:MONITOR_UNAVAILABLE:{iso(epoch)}", "MONITOR_UNAVAILABLE", "", "GitHub run metadata is unavailable; scheduler/source status unknown.")]
    report = {"checked_at": iso(now), "workflow_state": state, "released": released, "incidents": [asdict(item) for item in incidents], "recoveries": 0, "alerts_accepted": 0}
    if not released:
        return report
    with store.locked():
        problem_codes = {"MISSED_RUN", "RUN_FAILURE", "RUN_DURATION", "MONITOR_UNAVAILABLE", "WORKFLOW_DISABLED"}
        problems = [item for item in incidents if item.code in problem_codes]
        previous = store.connection.execute("SELECT value FROM health WHERE key='last_problem'").fetchone()
        if previous and previous[0] and not problems:
            store.enqueue("scheduler:RECOVERED:" + previous[0], "Ranking scheduler is responding again; source and message delivery are assessed separately.")
        current_problem = problems[-1].event_id if problems else ""
        store.connection.execute("INSERT OR REPLACE INTO health VALUES('last_problem',?)", (current_problem,))
        store.connection.commit()
        for item in incidents:
            store.enqueue(item.event_id, item.message)
            if item.recoverable and recovery_enabled and state == "active":
                attempt = store.reserve_recovery(item.slot, now)
                if attempt:
                    try:
                        client.dispatch()
                        result = "accepted"
                    except Exception:
                        result = "unknown_or_failed"
                    store.recovery_result(item.slot, attempt, result)
                    report["recoveries"] += 1
        report["alerts_accepted"] = store.flush(sender, now)
        store.connection.execute("INSERT OR REPLACE INTO health VALUES('last_check',?)", (iso(now),))
        store.connection.commit()
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("ATP_WATCHDOG_REPOSITORY", "hmono/Luka-Tennis-Player"))
    parser.add_argument("--state-dir", type=Path, default=Path(os.environ.get("ATP_WATCHDOG_STATE_DIR", "/var/lib/atp-ranking-watchdog")))
    parser.add_argument("--dry-run", action="store_true", help="Read metadata only; no local state writes, dispatch or alert")
    args = parser.parse_args(argv)
    client = GitHubActionsClient(args.repo, os.environ.get("ATP_WATCHDOG_GITHUB_TOKEN", ""))
    released = os.environ.get("ATP_RANKING_DELIVERY_ENABLED") == "true" and os.environ.get("ATP_WATCHDOG_ENABLED") == "true" and not args.dry_run
    if not released:
        # No SQLite/database directories in dry-run or before initial activation.
        report = watchdog_cycle(now=datetime.now(UTC), client=client, store=None, sender=webhook_sender, released=False, recovery_enabled=False)
    else:
        store = WatchdogStore(args.state_dir)
        try:
            report = watchdog_cycle(now=datetime.now(UTC), client=client, store=store, sender=webhook_sender, released=True, recovery_enabled=os.environ.get("ATP_WATCHDOG_RECOVERY_ENABLED") == "true")
        finally:
            store.close()
    print(json.dumps(report, sort_keys=True))
    return 1 if report["incidents"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
