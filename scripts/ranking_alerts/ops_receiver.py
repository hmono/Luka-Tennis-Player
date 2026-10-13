"""Independent durable operations inbox; HTTP acceptance is never device delivery.

Keep disabled until host, HTTPS proxy and a durable idempotent sink are qualified.
"""
from __future__ import annotations

import argparse
import contextlib
import hmac
import json
import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .autonomous_scheduler import _request, valid_destination


class OpsInbox:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / 'ops-inbox.sqlite3'
        self.forwarding_failures = 0
        with self.transaction() as database:
            if database.execute('PRAGMA journal_mode=WAL').fetchone()[0] != 'wal':
                raise sqlite3.OperationalError('wal_unavailable')
            database.execute('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, message TEXT NOT NULL, forwarded INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0)')
        # Persist the directory entry before serving any durable acceptance.
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def connect(self):
        database = sqlite3.connect(self.path, timeout=1)
        try:
            database.execute('PRAGMA synchronous=FULL')
        except Exception:
            database.close()
            raise
        return database

    @contextlib.contextmanager
    def transaction(self):
        database = self.connect()
        try:
            with database:
                yield database
        finally:
            database.close()

    def accept(self, event_id: str, message: str) -> bool:
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 256 or not isinstance(message, str) or not 1 <= len(message) <= 4096:
            raise ValueError('invalid_event')
        with self.transaction() as database:
            cursor = database.execute('INSERT OR IGNORE INTO events(id,message) VALUES(?,?)', (event_id, message))
            existing = database.execute('SELECT message FROM events WHERE id=?', (event_id,)).fetchone()
            if existing[0] != message:
                raise ValueError('event_id_conflict')
            created = cursor.rowcount == 1
        # The transaction context committed successfully before this return.
        return created

    def forward(self, sender) -> int:
        with self.transaction() as database:
            rows = database.execute('SELECT id,message FROM events WHERE forwarded=0 ORDER BY rowid LIMIT 100').fetchall()
        count = 0
        for event_id, message in rows:
            with self.transaction() as database:
                database.execute('UPDATE events SET attempts=attempts+1 WHERE id=?', (event_id,))
            try:
                accepted = sender(event_id, message)
            except Exception:
                accepted = False
            if accepted is True:
                with self.transaction() as database:
                    database.execute('UPDATE events SET forwarded=1 WHERE id=?', (event_id,))
                count += 1
        return count

    def status(self):
        with self.transaction() as database:
            count, pending = database.execute('SELECT count(*),coalesce(sum(forwarded=0),0) FROM events').fetchone()
        return {'persisted_events': count, 'pending_forwarding': pending,
                'forwarding_failures': self.forwarding_failures}


def forward_sender(event_id: str, message: str) -> bool:
    """The independent sink persists/deduplicates before a matching acknowledgment."""
    destination = os.environ.get('ATP_OPS_FORWARD_URL', '')
    token = os.environ.get('ATP_OPS_FORWARD_TOKEN', '')
    if not valid_destination(destination) or not token:
        return False
    response = _request(destination, token=token,
                        payload={'event_id': event_id, 'message': message}, event_id=event_id)
    return (isinstance(response, dict) and response.get('accepted') is True and
            response.get('event_id') == event_id)


def forward_loop(inbox: OpsInbox, sender, *, stop: threading.Event | None = None,
                 interval: float = 60) -> None:
    """Recover automatically even if SQLite fails before/after a send."""
    stop = stop or threading.Event()
    while not stop.is_set():
        try:
            inbox.forward(sender)
        except Exception:
            inbox.forwarding_failures += 1
        stop.wait(interval)


class BoundedInboxServer(ThreadingHTTPServer):
    """Bound workers as well as socket duration, including idle accepted sockets."""
    daemon_threads = True
    block_on_close = False
    request_queue_size = 8

    def __init__(self, address, handler, *, max_workers=4):
        self.workers = threading.BoundedSemaphore(max_workers)
        super().__init__(address, handler)

    def handle_error(self, *_):
        # Standard traceback logging can expose bodies, URLs and upstream details.
        pass

    def process_request(self, request, client_address):
        if not self.workers.acquire(blocking=False):
            body = b'{"error": "receiver_busy"}'
            try:
                request.settimeout(0.1)
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\nConnection: close\r\nRetry-After: 1\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.workers.release()
            self.shutdown_request(request)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.workers.release()


def handler_for(inbox: OpsInbox, token: str):
    class Handler(BaseHTTPRequestHandler):
        request_timeout = 5

        def setup(self):
            self.request.settimeout(self.request_timeout)
            super().setup()

        def log_message(self, *_):
            pass

        def respond(self, status, body):
            data = json.dumps(body).encode()
            self.close_connection = True
            try:
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Connection', 'close')
                if status == 503:
                    self.send_header('Retry-After', '1')
                self.end_headers()
                self.wfile.write(data)
            except OSError:
                pass  # Ack loss is recovered by event_id deduplication on retry.

        def authorized(self):
            values = self.headers.get_all('Authorization', [])
            return (bool(token) and len(values) == 1 and
                    hmac.compare_digest(values[0].encode('utf-8'), ('Bearer ' + token).encode('utf-8')))

        def do_GET(self):
            if not self.authorized():
                return self.respond(401, {'error': 'unauthorized'})
            if self.path != '/health':
                return self.respond(404, {'error': 'not_found'})
            try:
                value = inbox.status()
            except (sqlite3.Error, OSError):
                return self.respond(503, {'error': 'storage_unavailable'})
            return self.respond(200, value)

        def do_POST(self):
            if not self.authorized():
                return self.respond(401, {'error': 'unauthorized'})
            if self.path != '/events':
                return self.respond(404, {'error': 'not_found'})
            if len(self.headers.get_all('Content-Type', [])) != 1 or self.headers.get_content_type() != 'application/json':
                return self.respond(415, {'error': 'json_required'})
            try:
                lengths = self.headers.get_all('Content-Length', [])
                if len(lengths) != 1 or self.headers.get_all('Transfer-Encoding'):
                    raise ValueError('invalid_framing')
                if not lengths[0].isascii() or not lengths[0].isdigit():
                    raise ValueError('invalid_size')
                size = int(lengths[0])
                if not 0 < size <= 8192:
                    raise ValueError('invalid_size')
                payload = self.rfile.read(size)
                if len(payload) != size:
                    raise ValueError('truncated_body')
                value = json.loads(payload)
                if not isinstance(value, dict):
                    raise ValueError('invalid_event')
                created = inbox.accept(value['event_id'], value['message'])
            except TimeoutError:
                return self.respond(408, {'error': 'request_timeout'})
            except (sqlite3.Error, OSError):
                return self.respond(503, {'error': 'storage_unavailable'})
            except (ValueError, KeyError, TypeError, RecursionError) as error:
                if str(error) == 'event_id_conflict':
                    return self.respond(409, {'error': 'event_id_conflict'})
                return self.respond(400, {'error': 'invalid_event'})
            return self.respond(200, {'accepted': True, 'event_id': value['event_id'], 'duplicate': not created})
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=Path('/var/lib/atp-ops-inbox'))
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    token = os.environ.get('ATP_OPS_RECEIVER_TOKEN', '')
    if not token or os.environ.get('ATP_OPS_RECEIVER_ENABLED') != 'true':
        raise SystemExit('receiver_disabled_or_unconfigured')
    destination = os.environ.get('ATP_OPS_FORWARD_URL', '')
    if destination and (not valid_destination(destination) or not os.environ.get('ATP_OPS_FORWARD_TOKEN')):
        raise SystemExit('https_authenticated_forward_destination_required')
    try:
        inbox = OpsInbox(args.state_dir)
        server = BoundedInboxServer(('127.0.0.1', args.port), handler_for(inbox, token))
    except (sqlite3.Error, OSError, ValueError):
        raise SystemExit('receiver_storage_or_bind_unavailable') from None
    stop = threading.Event()
    if destination:
        threading.Thread(target=forward_loop, args=(inbox, forward_sender), kwargs={'stop': stop}, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
