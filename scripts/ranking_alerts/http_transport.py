"""Disposable HTTP worker. Invoked through private pipes by the watchdog.

The parent enforces the wall-clock deadline and kills/reaps a stalled worker.
This file uses only the standard library and does not read service credentials.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request


def exchange(value):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ranking-independent-watchdog",
               "X-GitHub-Api-Version": "2022-11-28"}
    if value["token"]:
        headers["Authorization"] = "Bearer " + value["token"]
    if value["event_id"]:
        headers["Idempotency-Key"] = hashlib.sha256(value["event_id"].encode()).hexdigest()
    data = None
    if value["payload"] is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(value["payload"], ensure_ascii=False).encode("utf-8")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    request = urllib.request.Request(value["url"], data=data, headers=headers)
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(request, timeout=value["timeout"]) as response:
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError("response_too_large")
        return json.loads(body) if body else {}


def main():
    try:
        value = json.loads(sys.stdin.buffer.read(2_000_001))
        result = {"ok": True, "result": exchange(value)}
    except urllib.error.HTTPError as error:
        # Retain only the status/cooldown metadata the scheduler needs.
        names = ("Retry-After", "X-RateLimit-Remaining", "X-RateLimit-Reset")
        result = {"ok": False, "error": "http_status", "status": error.code,
                  "headers": {name: error.headers[name] for name in names if name in error.headers}}
    except Exception:
        result = {"ok": False, "error": "http_transport_unavailable"}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
