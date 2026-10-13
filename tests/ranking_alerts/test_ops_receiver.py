"""Synthetic inbox contract tests; never contact a public destination."""
import contextlib
import http.client
import json
import os
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ranking_alerts import ops_receiver as receiver
from scripts.ranking_alerts.ops_receiver import OpsInbox, forward_loop, forward_sender


@contextlib.contextmanager
def local_receiver(inbox, *, max_workers=4, timeout=0.15):
    handler = receiver.handler_for(inbox, 'synthetic-token')
    handler.request_timeout = timeout
    server = receiver.BoundedInboxServer(('127.0.0.1', 0), handler, max_workers=max_workers)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01})
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
        if thread.is_alive():
            raise AssertionError('synthetic HTTP server did not stop')


def request(server, method='POST', path='/events', value=None, *, token='synthetic-token', body=None, headers=None):
    connection = http.client.HTTPConnection(*server.server_address, timeout=2)
    payload = json.dumps(value or {'event_id': 'synthetic:event', 'message': 'synthetic outage'}).encode() if body is None else body
    fields = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
    fields.update(headers or {})
    try:
        connection.request(method, path, payload if method == 'POST' else None, fields)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


class OpsInboxTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.inbox = OpsInbox(Path(self.directory.name) / 'inbox')

    def test_persistent_dedup_and_conflicting_ids(self):
        self.assertTrue(self.inbox.accept('event', 'synthetic outage'))
        restarted = OpsInbox(self.inbox.path.parent)
        self.assertFalse(restarted.accept('event', 'synthetic outage'))
        with self.assertRaisesRegex(ValueError, 'event_id_conflict'):
            restarted.accept('event', 'different')
        self.assertEqual(1, restarted.status()['persisted_events'])
        with sqlite3.connect(restarted.path) as database:
            self.assertEqual(('synthetic outage',), database.execute('SELECT message FROM events').fetchone())

    def test_wal_full_and_closed_owned_connections(self):
        connections = []
        original = self.inbox.connect
        def tracked():
            database = original()
            connections.append(database)
            self.assertEqual('wal', database.execute('PRAGMA journal_mode').fetchone()[0])
            self.assertEqual(2, database.execute('PRAGMA synchronous').fetchone()[0])
            return database
        with patch.object(self.inbox, 'connect', side_effect=tracked):
            self.inbox.accept('event', 'synthetic outage')
            self.inbox.status()
            self.inbox.forward(lambda *_: False)
        self.assertGreaterEqual(len(connections), 4)
        for database in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                database.execute('SELECT 1')

    def test_forwarding_outage_timeout_and_restart_retry_durable_sink(self):
        sink = OpsInbox(Path(self.directory.name) / 'synthetic-sink')
        self.inbox.accept('event', 'synthetic outage')
        self.assertEqual(0, self.inbox.forward(lambda *_: False))
        self.assertEqual(0, self.inbox.forward(lambda *_: (_ for _ in ()).throw(ConnectionError('synthetic unavailable'))))
        calls = []
        def lost_ack(event, message):
            calls.append(event)
            sink.accept(event, message)
            raise TimeoutError('synthetic ack lost after sink commit')
        self.assertEqual(0, self.inbox.forward(lost_ack))
        self.assertEqual(1, self.inbox.status()['pending_forwarding'])
        restarted = OpsInbox(self.inbox.path.parent)
        restarted_sink = OpsInbox(sink.path.parent)
        def durable_ack(event, message):
            calls.append(event)
            self.assertFalse(restarted_sink.accept(event, message))
            return True
        self.assertEqual(1, restarted.forward(durable_ack))
        self.assertEqual(0, restarted.forward(durable_ack))
        self.assertEqual(['event', 'event'], calls)
        self.assertEqual(1, restarted_sink.status()['persisted_events'])
        self.assertEqual(0, restarted.status()['pending_forwarding'])
        with sqlite3.connect(restarted.path) as database:
            self.assertEqual((4, 1), database.execute('SELECT attempts,forwarded FROM events').fetchone())

    def test_restart_replays_after_sink_commit_and_local_mark_failure(self):
        sink = OpsInbox(Path(self.directory.name) / 'synthetic-sink')
        self.inbox.accept('event', 'synthetic outage')
        original = self.inbox.connect
        calls = 0
        def fail_mark():
            nonlocal calls
            calls += 1
            if calls == 3:
                raise sqlite3.OperationalError('synthetic disk unavailable')
            return original()
        def sender(event, message):
            sink.accept(event, message)
            return True
        with patch.object(self.inbox, 'connect', side_effect=fail_mark):
            with self.assertRaises(sqlite3.OperationalError):
                self.inbox.forward(sender)
        restarted = OpsInbox(self.inbox.path.parent)
        self.assertEqual(1, restarted.status()['pending_forwarding'])
        self.assertEqual(1, restarted.forward(sender))
        self.assertEqual(1, sink.status()['persisted_events'])

    def test_real_database_lock_recovers_forwarding_without_service_restart(self):
        self.inbox.accept('event', 'synthetic outage')
        locked = self.inbox.connect()
        self.addCleanup(locked.close)
        locked.execute('BEGIN IMMEDIATE')
        stop, delivered = threading.Event(), threading.Event()
        def quick_connect():
            database = sqlite3.connect(self.inbox.path, timeout=0.02)
            database.execute('PRAGMA synchronous=FULL')
            return database
        def sender(*_):
            delivered.set()
            return True
        with patch.object(self.inbox, 'connect', side_effect=quick_connect):
            thread = threading.Thread(target=forward_loop, args=(self.inbox, sender), kwargs={'stop': stop, 'interval': 0.01})
            thread.start()
            try:
                deadline = time.monotonic() + 2
                while self.inbox.forwarding_failures == 0 and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertGreater(self.inbox.forwarding_failures, 0)
                self.assertTrue(thread.is_alive())
                self.assertFalse(delivered.is_set())
                locked.rollback()
                self.assertTrue(delivered.wait(2))
            finally:
                stop.set()
                thread.join(2)
                locked.rollback()
        self.assertFalse(thread.is_alive())
        self.assertEqual(0, self.inbox.status()['pending_forwarding'])

    def test_forwarding_requires_explicit_matching_durable_ack(self):
        self.inbox.accept('event', 'synthetic outage')
        with patch.dict(os.environ, {'ATP_OPS_FORWARD_URL': 'https://ops.example.test/events', 'ATP_OPS_FORWARD_TOKEN': 'synthetic-token'}, clear=True), patch('scripts.ranking_alerts.ops_receiver._request') as transport:
            for response in ({'accepted': False}, {}, {'accepted': 1}, {'accepted': True}, {'accepted': True, 'event_id': 'different'}, 'ok'):
                transport.return_value = response
                self.assertEqual(0, self.inbox.forward(forward_sender))
                self.assertEqual(1, self.inbox.status()['pending_forwarding'])
            transport.return_value = {'accepted': True, 'event_id': 'event'}
            self.assertEqual(1, self.inbox.forward(forward_sender))
            self.assertEqual(0, self.inbox.status()['pending_forwarding'])
            self.assertEqual('event', transport.call_args.kwargs['event_id'])
            self.assertEqual('synthetic-token', transport.call_args.kwargs['token'])

    def test_invalid_forward_configuration_never_contacts_destination(self):
        cases = [('http://ops.example.test/events', 'synthetic-token'), ('https:///events', 'synthetic-token'), ('https://user:pass@ops.example.test/events', 'synthetic-token'), ('https://ops.example.test/events#fragment', 'synthetic-token'), ('https://ops.example.test/events', '')]
        for destination, token in cases:
            with self.subTest(destination=destination), patch.dict(os.environ, {'ATP_OPS_FORWARD_URL': destination, 'ATP_OPS_FORWARD_TOKEN': token}, clear=True), patch('scripts.ranking_alerts.ops_receiver._request') as transport:
                self.assertFalse(forward_sender('event', 'synthetic outage'))
                transport.assert_not_called()

    def test_http_auth_paths_acceptance_conflict_and_restart(self):
        with local_receiver(self.inbox) as server:
            self.assertEqual(401, request(server, token='wrong')[0])
            self.assertEqual(401, request(server, token='caf\xe9')[0])
            self.assertEqual(404, request(server, path='/missing')[0])
            status, body = request(server)
            self.assertEqual(200, status)
            self.assertEqual({'accepted': True, 'event_id': 'synthetic:event', 'duplicate': False}, body)
            self.assertEqual(1, OpsInbox(self.inbox.path.parent).status()['persisted_events'])
            self.assertTrue(request(server)[1]['duplicate'])
            self.assertEqual((409, {'error': 'event_id_conflict'}), request(server, value={'event_id': 'synthetic:event', 'message': 'changed'}))
            self.assertEqual(1, request(server, 'GET', '/health')[1]['persisted_events'])

    def test_http_payload_bounds_and_json_shapes_never_accept(self):
        invalid = [b'', b'x' * 8193, b'{', b'\xff', b'[]', b'null', b'1', b'"text"', b'[' * 1500 + b']' * 1500, b'{"event_id": "event"}', json.dumps({'event_id': '', 'message': 'x'}).encode(), json.dumps({'event_id': 'x' * 257, 'message': 'x'}).encode(), json.dumps({'event_id': 'x', 'message': 'x' * 4097}).encode(), json.dumps({'event_id': 1, 'message': 'x'}).encode()]
        with local_receiver(self.inbox) as server:
            for body in invalid:
                with self.subTest(size=len(body)):
                    self.assertEqual(400, request(server, body=body)[0])
            self.assertEqual(415, request(server, headers={'Content-Type': 'text/plain'})[0])
        self.assertEqual(0, self.inbox.status()['persisted_events'])

    def test_http_accepts_exact_character_bounds(self):
        with local_receiver(self.inbox) as server:
            status, body = request(server, value={'event_id': 'x' * 256, 'message': 'y' * 4096})
            self.assertEqual((200, True), (status, body['accepted']))
        self.assertEqual(1, self.inbox.status()['persisted_events'])

    def test_http_timeout_rejects_partial_body_without_acceptance(self):
        with local_receiver(self.inbox, timeout=0.05) as server:
            with socket.create_connection(server.server_address, timeout=1) as connection:
                connection.settimeout(1)
                connection.sendall(b'POST /events HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer synthetic-token\r\nContent-Type: application/json\r\nContent-Length: 50\r\n\r\n{')
                self.assertIn(b'408', connection.recv(4096))
            self.assertEqual(0, self.inbox.status()['persisted_events'])

    def test_http_rejects_truncated_eof_and_ambiguous_framing(self):
        with local_receiver(self.inbox) as server:
            cases = [(b'Content-Length: 10\r\n', b'{}'), (b'Content-Length: 2\r\nContent-Length: 2\r\n', b'{}'), (b'Content-Length: 2\r\nTransfer-Encoding: chunked\r\n', b'{}'), (b'Content-Length: -1\r\n', b'{}'), (b'Content-Length: +2\r\n', b'{}')]
            for extra, payload in cases:
                with socket.create_connection(server.server_address, timeout=1) as connection:
                    connection.settimeout(1)
                    connection.sendall(b'POST /events HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer synthetic-token\r\nContent-Type: application/json\r\n' + extra + b'\r\n' + payload)
                    connection.shutdown(socket.SHUT_WR)
                    self.assertIn(b'400', connection.recv(4096))
        self.assertEqual(0, self.inbox.status()['persisted_events'])

    def test_http_lock_returns_retryable_503_then_recovers(self):
        locked = self.inbox.connect()
        self.addCleanup(locked.close)
        locked.execute('BEGIN IMMEDIATE')
        def quick_connect():
            database = sqlite3.connect(self.inbox.path, timeout=0.02)
            database.execute('PRAGMA synchronous=FULL')
            return database
        with local_receiver(self.inbox) as server, patch.object(self.inbox, 'connect', side_effect=quick_connect):
            self.assertEqual((503, {'error': 'storage_unavailable'}), request(server))
            self.assertEqual(0, request(server, 'GET', '/health')[1]['persisted_events'])
            locked.rollback()
            self.assertTrue(request(server)[1]['accepted'])

    def test_http_failed_commit_never_returns_accepted(self):
        original = self.inbox.connect
        class CommitFailure:
            def __init__(self):
                self.database = original()
            def __enter__(self):
                return self.database
            def __exit__(self, *_):
                self.database.rollback()
                self.database.close()
                raise sqlite3.OperationalError('synthetic commit/fsync failure')
        with local_receiver(self.inbox) as server, patch.object(self.inbox, 'transaction', side_effect=CommitFailure):
            self.assertEqual((503, {'error': 'storage_unavailable'}), request(server))
        self.assertEqual(0, OpsInbox(self.inbox.path.parent).status()['persisted_events'])

    def test_http_ack_only_after_visible_commit(self):
        with local_receiver(self.inbox) as server:
            status, body = request(server)
            self.assertEqual((200, True), (status, body['accepted']))
            with sqlite3.connect(self.inbox.path) as database:
                self.assertEqual(('synthetic outage',), database.execute('SELECT message FROM events WHERE id=?', (body['event_id'],)).fetchone())

    def test_http_worker_cap_returns_sanitized_overload_and_recovers(self):
        entered, release = threading.Event(), threading.Event()
        original = self.inbox.accept
        result = []
        def held_accept(*args):
            entered.set()
            if not release.wait(2):
                raise AssertionError('synthetic worker not released')
            return original(*args)
        with local_receiver(self.inbox, max_workers=1) as server, patch.object(self.inbox, 'accept', side_effect=held_accept):
            thread = threading.Thread(target=lambda: result.append(request(server)))
            thread.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertEqual((503, {'error': 'receiver_busy'}), request(server))
            finally:
                release.set()
                thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(200, result[0][0])
        self.assertEqual(1, self.inbox.status()['persisted_events'])

    def test_startup_requires_release_and_sanitizes_storage_failure(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SystemExit, 'receiver_disabled_or_unconfigured'):
                receiver.main([])
        with patch.dict(os.environ, {'ATP_OPS_RECEIVER_ENABLED': 'true', 'ATP_OPS_RECEIVER_TOKEN': 'synthetic-token'}, clear=True), patch.object(receiver, 'OpsInbox', side_effect=sqlite3.OperationalError('sensitive fake detail')):
            with self.assertRaisesRegex(SystemExit, '^receiver_storage_or_bind_unavailable$'):
                receiver.main(['--state-dir', str(self.inbox.path.parent)])


if __name__ == '__main__':
    unittest.main()
