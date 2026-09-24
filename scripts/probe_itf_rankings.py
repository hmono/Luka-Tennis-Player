#!/usr/bin/env python3
"""Read-only qualification probe for ITF player API ranking data.

Opens the public ITF player page in headless Chromium (same access method as
update_career.py), records every PlayerApi response the SPA issues, then calls
candidate ranking endpoints with the session cookies. Prints sanitized output
only: URL path, status, top-level keys and a bounded JSON excerpt. Nothing is
persisted and no notification is sent.
"""
from __future__ import annotations

import json
import re

PLAYER_ID = "800625103"
BASE = "https://www.itftennis.com"
OVERVIEW_URL = f"{BASE}/en/players/luka-bojicic-ono/{PLAYER_ID}/bra/mt/s/overview/"
CANDIDATES = [
    f"/tennis/api/PlayerApi/GetPlayerProfile?playerId={PLAYER_ID}&circuitCode=MT",
    f"/tennis/api/PlayerApi/GetPlayerRankings?playerId={PLAYER_ID}&circuitCode=MT",
    f"/tennis/api/PlayerApi/GetPlayerRankingHistory?playerId={PLAYER_ID}&circuitCode=MT",
    f"/tennis/api/PlayerApi/GetPlayerOverview?playerId={PLAYER_ID}&circuitCode=MT",
    f"/tennis/api/PlayerApi/GetPlayerHeader?playerId={PLAYER_ID}&circuitCode=MT",
]
EXCERPT = 3000
KEY_RE = re.compile(r"rank|point|date", re.I)


def _keys_of_interest(obj, prefix="", out=None):
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if KEY_RE.search(k) and not isinstance(v, (dict, list)):
                out.append(f"  {path} = {v!r}")
            _keys_of_interest(v, path, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:5]):
            _keys_of_interest(v, f"{prefix}[{i}]", out)
    return out


def _report(label: str, status: int, body: str) -> None:
    print(f"===== {label} status={status} bytes={len(body)}")
    try:
        payload = json.loads(body)
    except ValueError:
        print("  non-json body; excerpt:")
        print("  " + body[:500].replace("\n", " "))
        return
    top = list(payload.keys()) if isinstance(payload, dict) else f"list[{len(payload)}]"
    print(f"  top-level: {top}")
    for line in _keys_of_interest(payload):
        print(line)
    print("  excerpt: " + json.dumps(payload)[:EXCERPT])


def main() -> int:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        seen: list[tuple[str, int, str]] = []

        def on_response(response):
            if "/tennis/api/" in response.url:
                try:
                    seen.append((response.url.replace(BASE, ""), response.status, response.text()))
                except Exception as exc:  # noqa: BLE001
                    seen.append((response.url.replace(BASE, ""), response.status, f"<unreadable: {exc}>"))

        page.on("response", on_response)
        try:
            page.goto(OVERVIEW_URL, timeout=60_000, wait_until="networkidle")
        except PWTimeout:
            print("page load timed out; continuing")
        print(f"page status: title={page.title()!r}")

        text = page.inner_text("body")
        for m in re.finditer(r"(?i)rank[^\n]{0,80}\n[^\n]{0,80}\n[^\n]{0,80}", text):
            print("  body-text: " + m.group(0).replace("\n", " | "))

        print(f"===== SPA api calls observed: {len(seen)}")
        for url, status, body in seen:
            _report(f"SPA {url}", status, body)

        for path in CANDIDATES:
            try:
                resp = context.request.get(BASE + path, timeout=30_000)
                _report(f"CANDIDATE {path}", resp.status, resp.text())
            except Exception as exc:  # noqa: BLE001
                print(f"===== CANDIDATE {path} error={type(exc).__name__}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
