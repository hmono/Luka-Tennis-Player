"""Independent Ops26 regressions; synthetic metadata and isolated SQLite only."""
from __future__ import annotations

import contextlib
import json
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.ranking_alerts import autonomous_scheduler as scheduler
from scripts.ranking_alerts import ops_receiver as receiver


NOW = datetime(2026, 10, 13, 14, tzinfo=timezone.utc)


@contextlib.contextmanager
def serving(server):
    """Only ephemeral loopback sockets; no installed service or real endpoint."""
    original_run = subprocess.run

    def isolated_run(*args, **kwargs):
        # Child fixtures have no inherited credentials or proxy configuration.
        kwargs['env'] = {'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1',
                         'NO_PROXY': '127.0.0.1,localhost'}
        return original_run(*args, **kwargs)

    worker = threading.Thread(target=server.serve_forever,
                              kwargs={'poll_interval': 0.01})
    worker.start()
    try:
        with patch.object(subprocess, 'run', side_effect=isolated_run):
            yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)
        if worker.is_alive():
            raise AssertionError('synthetic server did not stop')


def successful_run(created: datetime, identity: int = 1) -> dict:
    return {
        'id': identity,
        'event': 'schedule',
        'head_branch': 'main',
        'created_at': scheduler.iso(created),
        'run_started_at': scheduler.iso(created + timedelta(minutes=1)),
        'updated_at': scheduler.iso(created + timedelta(minutes=5)),
        'status': 'completed',
        'conclusion': 'success',
    }


class Ops26AdversarialTests(unittest.TestCase):
    def test_old_history_does_not_permanently_disable_observation(self):
        """500 retained runs must not hide a healthy run in the latest slot."""
        recent = successful_run(NOW.replace(hour=12, minute=18))
        runs = [recent] + [successful_run(NOW - timedelta(days=i), i + 1)
                           for i in range(1, 500)]
        client = scheduler.GitHubActionsClient('synthetic/repo', '')

        def response(url, *, payload=None):
            self.assertIsNone(payload, 'No remote mutation is permitted in this fixture')
            if url == client.base:
                return {'state': 'active'}
            # The fixture serves an ordinary retained history, including old
            # rows. A fixed client may paginate only the relevant date range.
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(url).query)
            selected = runs
            if 'created' in query:
                criterion = query['created'][0]
                lower = criterion.split('..')[0].lstrip('>=')
                boundary = scheduler.parse(lower)
                selected = [row for row in runs
                            if scheduler.parse(row['created_at']) >= boundary]
            page = int(query.get('page', ['1'])[0])
            return {'total_count': len(selected),
                    'workflow_runs': selected[(page - 1) * 100:page * 100]}

        with patch.object(client, '_api_request', side_effect=response), \
                patch.object(scheduler, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = NOW
            report = scheduler.watchdog_cycle(
                now=NOW, client=client, store=None, sender=Mock(),
                released=False, recovery_enabled=False)
        self.assertEqual('active', report['workflow_state'])
        self.assertEqual([], report['incidents'])

    def test_exactly_500_recent_runs_are_complete_but_501_fail_closed(self):
        for total in (500, 501):
            with self.subTest(total=total):
                runs = [successful_run(NOW - timedelta(minutes=i + 1), i + 1)
                        for i in range(total)]
                client = scheduler.GitHubActionsClient('synthetic/repo', '')
                pages = []

                def response(url, *, payload=None):
                    self.assertIsNone(payload)
                    if url == client.base:
                        return {'state': 'active'}
                    from urllib.parse import parse_qs, urlparse
                    query = parse_qs(urlparse(url).query)
                    self.assertIn('created', query)
                    page = int(query['page'][0])
                    pages.append(page)
                    return {'total_count': total,
                            'workflow_runs': runs[(page - 1) * 100:page * 100]}

                with patch.object(client, '_api_request', side_effect=response):
                    if total == 500:
                        state, observed = client.inspect()
                        self.assertEqual(('active', 500), (state, len(observed)))
                    else:
                        with self.assertRaisesRegex(ValueError, 'run_metadata_truncated'):
                            client.inspect()
                self.assertEqual([1, 2, 3, 4, 5], pages)

    def test_a_new_disable_episode_is_delivered_after_recovery_and_restart(self):
        """Lifetime dedup must not suppress every later disabled-workflow event."""
        client = Mock()
        client.inspect.side_effect = [
            ('disabled_manually', []),
            ('active', [successful_run(NOW.replace(hour=12, minute=18))]),
            ('disabled_manually', []),
        ]
        accepted = []

        def sender(event_id, message):
            accepted.append((event_id, message))
            return True

        with tempfile.TemporaryDirectory(prefix='ops26-independent-') as directory:
            for minute in (0, 10, 20):
                store = scheduler.WatchdogStore(Path(directory))
                try:
                    scheduler.watchdog_cycle(
                        now=NOW + timedelta(minutes=minute), client=client,
                        store=store, sender=sender, released=True,
                        recovery_enabled=False)
                finally:
                    store.close()
        disabled = [(identity, message) for identity, message in accepted
                    if 'workflow is disabled' in message]
        self.assertEqual(2, len(disabled), accepted)
        self.assertNotEqual(disabled[0][0], disabled[1][0])
        client.dispatch.assert_not_called()

    def test_unobserved_recovery_never_rekeys_an_existing_disable_episode(self):
        client = Mock()
        client.inspect.side_effect = [
            ('disabled_manually', []), TimeoutError('synthetic metadata outage'),
            ('disabled_manually', []), ('disabled_manually', []),
        ]
        disabled_ids = []

        def sender(event_id, message):
            if 'workflow is disabled' in message:
                disabled_ids.append(event_id)
            # Simulate ack loss so the original event must be replayed.
            return False

        with tempfile.TemporaryDirectory(prefix='ops26-independent-') as directory:
            for minute in (0, 10, 20, 30):
                store = scheduler.WatchdogStore(Path(directory))
                try:
                    scheduler.watchdog_cycle(
                        now=NOW + timedelta(minutes=minute), client=client,
                        store=store, sender=sender, released=True,
                        recovery_enabled=False)
                finally:
                    store.close()
        self.assertGreaterEqual(len(disabled_ids), 3)
        self.assertEqual(1, len(set(disabled_ids)))
        client.dispatch.assert_not_called()

    def test_header_and_body_drips_hit_total_deadline_and_leave_no_child(self):
        for phase in ('headers', 'body'):
            with self.subTest(phase=phase):
                stop, entered = threading.Event(), threading.Event()

                class Drip(BaseHTTPRequestHandler):
                    def log_message(self, *_):
                        pass

                    def do_GET(self):
                        if self.path == '/ready':
                            body = b'{"ready": true}'
                            self.send_response(200)
                            self.send_header('Content-Length', str(len(body)))
                            self.end_headers()
                            self.wfile.write(body)
                            return
                        entered.set()
                        try:
                            if phase == 'headers':
                                self.wfile.write(b'HTTP/1.1 200 OK\r\nX-Synthetic: ')
                            else:
                                self.send_response(200)
                                self.send_header('Content-Length', '2000')
                                self.end_headers()
                            for _ in range(100):
                                if stop.is_set():
                                    return
                                self.wfile.write(b' ')
                                self.wfile.flush()
                                stop.wait(0.02)
                        except (BrokenPipeError, ConnectionResetError):
                            pass

                children = []
                original_popen = subprocess.Popen

                def track_child(*args, **kwargs):
                    child = original_popen(*args, **kwargs)
                    children.append(child)
                    return child

                with serving(HTTPServer(('127.0.0.1', 0), Drip)) as url:
                    try:
                        begin = time.monotonic()
                        with patch.object(scheduler, 'HTTP_REQUEST_DEADLINE', 0.5), \
                                patch.object(subprocess, 'Popen', side_effect=track_child):
                            with self.assertRaisesRegex(TimeoutError, 'http_deadline_exceeded'):
                                scheduler._request(url + '/slow')
                        self.assertTrue(entered.is_set(), 'fixture must reach the stalled phase')
                        self.assertLess(time.monotonic() - begin, 2)
                        self.assertEqual(1, len(children))
                        self.assertIsNotNone(children[0].poll(), 'timed out child was not reaped')
                    finally:
                        stop.set()
                    self.assertEqual({'ready': True}, scheduler._request(url + '/ready'))

    def test_valid_utf8_event_reaches_an_equally_bounded_sink(self):
        event_id, message = 'synthetic:unicode', 'é' * 2000
        body = json.dumps({'event_id': event_id, 'message': message},
                          ensure_ascii=False).encode('utf-8')
        self.assertLess(len(body), 8192)
        with tempfile.TemporaryDirectory(prefix='ops26-independent-') as directory:
            origin = receiver.OpsInbox(Path(directory) / 'origin')
            sink = receiver.OpsInbox(Path(directory) / 'sink')
            origin.accept(event_id, message)
            server = receiver.BoundedInboxServer(
                ('127.0.0.1', 0), receiver.handler_for(sink, 'synthetic-token'))
            with serving(server) as url:
                def sender(identity, content):
                    ack = scheduler._request(
                        url + '/events', token='synthetic-token',
                        payload={'event_id': identity, 'message': content},
                        event_id=identity)
                    return ack.get('accepted') is True and ack.get('event_id') == identity

                self.assertEqual(1, origin.forward(sender))
            self.assertEqual(0, origin.status()['pending_forwarding'])
            with sink.transaction() as database:
                self.assertEqual((message,), database.execute(
                    'SELECT message FROM events WHERE id=?', (event_id,)).fetchone())

    def test_http_worker_preserves_cooldown_and_never_follows_redirect(self):
        paths = []

        class StatusEndpoint(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                paths.append(self.path)
                if self.path.startswith('/rate'):
                    body = b'synthetic-private-body'
                    self.send_response(429)
                    self.send_header('Retry-After', '1800')
                    self.send_header('X-RateLimit-Remaining', '0')
                    self.send_header('X-RateLimit-Reset', '1791900000')
                    self.send_header('X-Private-Fixture', 'synthetic-private-header')
                elif self.path == '/redirect':
                    body = b''
                    self.send_response(302)
                    self.send_header('Location', '/must-not-be-requested')
                else:
                    body = b'{}'
                    self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with serving(HTTPServer(('127.0.0.1', 0), StatusEndpoint)) as url:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                scheduler._request(url + '/rate?synthetic-private-url',
                                   token='synthetic-private-token')
            error = raised.exception
            self.assertEqual(429, error.code)
            self.assertEqual({'Retry-After': '1800', 'X-RateLimit-Remaining': '0',
                              'X-RateLimit-Reset': '1791900000'}, error.headers)
            self.assertEqual('', error.url)
            self.assertEqual('http_status', error.reason)
            self.assertNotIn('synthetic-private', str(vars(error)))

            with self.assertRaises(urllib.error.HTTPError) as redirected:
                scheduler._request(url + '/redirect', token='synthetic-private-token')
            self.assertEqual(302, redirected.exception.code)
        self.assertEqual(['/rate?synthetic-private-url', '/redirect'], paths)


if __name__ == '__main__':
    unittest.main()
