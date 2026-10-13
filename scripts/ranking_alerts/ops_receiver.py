"""Reference independent durable operations inbox with idempotent event IDs.

Run outside GitHub behind HTTPS. Durable acceptance is not device delivery.
Optional outbound webhook forwarding retries from disk, with possible duplicate
forwarding on ambiguous HTTP; inbox deduplication is exact by event_id.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import sqlite3
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .autonomous_scheduler import _request


class OpsInbox:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / 'ops-inbox.sqlite3'
        with self.connect() as database:
            database.execute('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, message TEXT NOT NULL, forwarded INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0)')

    def connect(self):
        database = sqlite3.connect(self.path, timeout=30)
        database.execute('PRAGMA synchronous=FULL')
        return database

    def accept(self, event_id: str, message: str) -> bool:
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 256 or not isinstance(message, str) or not 1 <= len(message) <= 4096:
            raise ValueError('invalid_event')
        with self.connect() as database:
            cursor = database.execute('INSERT OR IGNORE INTO events(id,message) VALUES(?,?)', (event_id, message))
            existing = database.execute('SELECT message FROM events WHERE id=?', (event_id,)).fetchone()
            if existing[0] != message:
                raise ValueError('event_id_conflict')
            return cursor.rowcount == 1

    def forward(self, sender) -> int:
        with self.connect() as database:
            rows = database.execute('SELECT id,message FROM events WHERE forwarded=0 ORDER BY rowid LIMIT 100').fetchall()
        count = 0
        for event_id, message in rows:
            with self.connect() as database:
                database.execute('UPDATE events SET attempts=attempts+1 WHERE id=?', (event_id,))
            try:
                accepted = sender(event_id, message)
            except Exception:
                accepted = False
            if accepted:
                with self.connect() as database:
                    database.execute('UPDATE events SET forwarded=1 WHERE id=?', (event_id,))
                count += 1
        return count

    def status(self):
        with self.connect() as database:
            count, pending = database.execute('SELECT count(*),coalesce(sum(forwarded=0),0) FROM events').fetchone()
        return {'persisted_events': count, 'pending_forwarding': pending}


def handler_for(inbox: OpsInbox, token: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never print credentials, URLs, request bodies or upstream errors.

        def respond(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            return bool(token) and hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token)

        def do_GET(self):
            if not self.authorized():
                return self.respond(401, {'error': 'unauthorized'})
            if self.path != '/health':
                return self.respond(404, {'error': 'not_found'})
            return self.respond(200, inbox.status())

        def do_POST(self):
            if not self.authorized():
                return self.respond(401, {'error': 'unauthorized'})
            if self.path != '/events':
                return self.respond(404, {'error': 'not_found'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8192:
                    raise ValueError('invalid_size')
                value = json.loads(self.rfile.read(size))
                created = inbox.accept(value['event_id'], value['message'])
            except (ValueError, KeyError, TypeError):
                return self.respond(400, {'error': 'invalid_event'})
            return self.respond(200, {'accepted': True, 'duplicate': not created})
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=Path('/var/lib/atp-ops-inbox'))
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    token = os.environ.get('ATP_OPS_RECEIVER_TOKEN', '')
    if not token or os.environ.get('ATP_OPS_RECEIVER_ENABLED') != 'true':
        raise SystemExit('receiver_disabled_or_unconfigured')
    inbox = OpsInbox(args.state_dir)
    destination = os.environ.get('ATP_OPS_FORWARD_URL', '')
    if destination:
        if urllib.parse.urlparse(destination).scheme != 'https':
            raise SystemExit('https_forward_url_required')
        def sender(event_id, message):
            _request(destination, token=os.environ.get('ATP_OPS_FORWARD_TOKEN', ''), payload={'event_id': event_id, 'message': message}, event_id=event_id)
            return True
        def forward_loop():
            wait = threading.Event()
            while True:
                inbox.forward(sender)
                wait.wait(60)
        threading.Thread(target=forward_loop, daemon=True).start()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(inbox, token))
    server.serve_forever()


if __name__ == '__main__':
    main()
