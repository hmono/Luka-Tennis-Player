from __future__ import annotations

import json
import base64
import contextlib
import io
import multiprocessing
import os
import sqlite3
import subprocess
import tempfile
import urllib.error
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.ranking_alerts.autonomous_scheduler import (
    GitHubActionsClient, WatchdogStore, assess_runs, iso, main, poll_slots,
    send_operational_alert, watchdog_cycle, weekly_period, webhook_sender,
)


def at(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


@contextlib.contextmanager
def app_credentials():
    # Synthetic marker only; signing is mocked unless a test generates its own key.
    with tempfile.TemporaryDirectory() as directory:
        key = Path(directory) / 'fixture.pem'
        key.write_text('SYNTHETIC TEST KEY, NOT A CREDENTIAL')
        key.chmod(0o640)
        with patch.dict(os.environ, {'ATP_WATCHDOG_APP_ID': '123',
                                   'ATP_WATCHDOG_APP_INSTALLATION_ID': '456',
                                   'ATP_WATCHDOG_APP_PRIVATE_KEY_PATH': str(key)}, clear=True):
            yield key


def run(slot, **overrides):
    value = dict(id=1, event='schedule', head_branch='main', created_at=iso(slot + timedelta(minutes=1)),
                 run_started_at=iso(slot + timedelta(minutes=2)), updated_at=iso(slot + timedelta(minutes=8)),
                 status='completed', conclusion='success')
    value.update(overrides)
    return value


class Client:
    def __init__(self, state='active', runs=None, failure=False):
        self.state, self.runs, self.failure = state, runs or [], failure
        self.dispatches = 0

    def inspect(self):
        if self.failure:
            raise TimeoutError('sensitive response')
        return self.state, self.runs

    def dispatch(self):
        self.dispatches += 1


def concurrent_recovery(clone, state_dir, output):
    # Different real checkouts sharing one external host's persistent volume.
    os.chdir(clone)
    client = Client()
    store = WatchdogStore(Path(state_dir))
    try:
        result = watchdog_cycle(now=at('2026-10-13T14:00:00Z'), client=client, store=store,
                                sender=lambda *_: True, released=True, recovery_enabled=True)
        Path(output).write_text(json.dumps(result))
    finally:
        store.close()


class AutonomousSchedulerTests(unittest.TestCase):
    def test_weekly_boundary_is_sao_paulo_and_polling_includes_weekends(self):
        self.assertEqual('2026-10-05', weekly_period(at('2026-10-12T11:59:59Z')))
        self.assertEqual('2026-10-12', weekly_period(at('2026-10-12T12:00:00Z')))
        self.assertEqual('2026-10-12', weekly_period(at('2026-10-12T09:00:00-03:00')))
        self.assertEqual('2026-10-11T18:17:00Z', iso(poll_slots(at('2026-10-11T20:00:00Z'))[-1]))
        with self.assertRaises(ValueError):
            weekly_period(datetime(2026, 10, 12))

    def test_eight_weeks_without_calendar_and_with_source_changes(self):
        # Scheduler period selection never takes source date/rank as an input.
        start = at('2026-10-12T12:17:00Z')
        for scenario in ('no_editions', 'delayed', 'same_rank_new_editions'):
            periods = set()
            slots = set()
            source_date = '2026-10-05'
            for day in range(56):
                for hour in (12, 18):
                    now = (start + timedelta(days=day)).replace(hour=hour)
                    periods.add(weekly_period(now))
                    slots.add(iso(poll_slots(now)[-1]))
                    if scenario == 'delayed' and day == 17:
                        source_date = '2026-10-19'
                    if scenario == 'same_rank_new_editions' and day % 7 == 0:
                        source_date = now.date().isoformat()
                    self.assertTrue(source_date)
            self.assertEqual(8, len(periods))
            self.assertEqual(112, len(slots))

    def test_missing_failure_delay_duration_and_main_filter(self):
        now = at('2026-10-13T14:00:00Z')
        slot = at('2026-10-13T12:17:00Z')
        self.assertEqual(['MISSED_RUN'], [i.code for i in assess_runs(now, [])])
        self.assertEqual([], assess_runs(at('2026-10-13T13:46:00Z'), [run(at('2026-10-12T18:17:00Z'))]))
        self.assertEqual([], assess_runs(now, [run(slot)]))
        self.assertEqual(['RUN_FAILURE'], [i.code for i in assess_runs(now, [run(slot, conclusion='failure')])])
        delayed = run(slot, run_started_at='2026-10-13T13:30:00Z', updated_at='2026-10-13T13:55:00Z')
        self.assertEqual({'SCHEDULER_DELAY', 'RUN_DURATION'}, {i.code for i in assess_runs(now, [delayed])})
        hanging = run(slot, status='in_progress')
        self.assertEqual(['RUN_DURATION'], [i.code for i in assess_runs(now, [hanging])])
        self.assertEqual(['MISSED_RUN'], [i.code for i in assess_runs(now, [run(slot, head_branch='feature')])])
        self.assertEqual(['MISSED_RUN'], [i.code for i in assess_runs(now, [run(slot, event='workflow_dispatch', display_title='ATP rankings dry-run')])])
        self.assertEqual([], assess_runs(now, [run(slot, event='workflow_dispatch', display_title='ATP rankings collect-and-deliver')]))

    def test_external_outage_dedup_backoff_bound_and_automatic_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WatchdogStore(Path(directory))
            client, accepted = Client(), []
            now = at('2026-10-13T14:00:00Z')
            sender = lambda event, message: accepted.append(event) or True
            for minute in (0, 5, 10, 30, 60):
                watchdog_cycle(now=now + timedelta(minutes=minute), client=client, store=store,
                               sender=sender, released=True, recovery_enabled=True)
            self.assertEqual(2, client.dispatches)
            self.assertEqual(1, len(accepted))
            client.runs = [run(at('2026-10-13T12:17:00Z'), event='workflow_dispatch', display_title='ATP rankings collect-and-deliver', created_at='2026-10-13T14:00:00Z', run_started_at='2026-10-13T14:00:00Z', updated_at='2026-10-13T14:01:00Z')]
            result = watchdog_cycle(now=now + timedelta(minutes=70), client=client, store=store,
                                    sender=sender, released=True, recovery_enabled=True)
            self.assertNotIn('MISSED_RUN', [item['code'] for item in result['incidents']])
            self.assertEqual(2, client.dispatches)
            store.close()

    def test_pending_ops_retries_and_disabled_workflow_is_never_dispatched(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WatchdogStore(Path(directory))
            client = Client(state='disabled_manually')
            now = at('2026-10-13T14:00:00Z')
            first = watchdog_cycle(now=now, client=client, store=store, sender=lambda *_: False,
                                   released=True, recovery_enabled=True)
            second = watchdog_cycle(now=now + timedelta(minutes=10), client=client, store=store,
                                    sender=lambda *_: True, released=True, recovery_enabled=True)
            self.assertEqual(0, first['alerts_accepted'])
            self.assertEqual(1, second['alerts_accepted'])
            self.assertEqual(0, client.dispatches)
            self.assertEqual(1, store.connection.execute('SELECT count(*) FROM alerts').fetchone()[0])
            store.close()

    def test_github_metadata_outage_is_sanitized_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WatchdogStore(Path(directory))
            accepted = []
            for minute in (0, 10, 20):
                report = watchdog_cycle(now=at('2026-10-13T14:00:00Z') + timedelta(minutes=minute), client=Client(failure=True), store=store,
                                        sender=lambda e, m: accepted.append(e) or True, released=True, recovery_enabled=True)
                self.assertNotIn('sensitive', json.dumps(report))
            self.assertEqual(1, len(accepted))
            store.close()

    def test_initial_release_and_dry_run_have_no_writes_or_sends(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'absent'
            with patch.dict(os.environ, {'ATP_WATCHDOG_ENABLED': 'true', 'ATP_RANKING_DELIVERY_ENABLED': 'true'}, clear=True), patch.object(GitHubActionsClient, 'inspect', return_value=('disabled_manually', [])), patch.object(GitHubActionsClient, 'dispatch') as dispatch, patch('scripts.ranking_alerts.autonomous_scheduler.webhook_sender') as sender:
                main(['--dry-run', '--state-dir', str(state)])
            self.assertFalse(state.exists())
            dispatch.assert_not_called()
            sender.assert_not_called()
            with patch.dict(os.environ, {}, clear=True):
                self.assertFalse(send_operational_alert('id', 'message'))

    def test_app_installation_token_renews_automatically_without_exposing_key(self):
        with app_credentials(), patch('scripts.ranking_alerts.autonomous_scheduler.subprocess.run') as sign, patch('scripts.ranking_alerts.autonomous_scheduler._request') as request:
            sign.return_value.stdout = b"fixture-signature"
            request.return_value = {"token": "new-installation-token", "expires_at": "2099-10-13T16:00:00Z"}
            client = GitHubActionsClient('owner/repo', '')
            self.assertEqual('new-installation-token', client.authentication_token())
            self.assertEqual('new-installation-token', client.authentication_token())
            self.assertEqual(1, request.call_count)
            claims_segment = sign.call_args.kwargs['input'].decode().split('.')[1]
            claims = json.loads(base64.urlsafe_b64decode(claims_segment + '=' * (-len(claims_segment) % 4)))
            self.assertEqual(600, claims['exp'] - claims['iat'])
            self.assertEqual('123', claims['iss'])
            client.token_expires = at('2000-01-01T00:00:00Z')
            client.authentication_token()
            self.assertEqual(2, request.call_count)

    def test_ops_sink_requires_durable_ack_contract_not_only_http_acceptance(self):
        with patch.dict(os.environ, {'ATP_OPS_WEBHOOK_URL': 'https://ops.example.test/events'}, clear=True), patch('scripts.ranking_alerts.autonomous_scheduler._request') as request:
            request.return_value = {}
            self.assertFalse(webhook_sender('event', 'status unknown'))
            request.return_value = {'accepted': True}
            self.assertTrue(webhook_sender('event', 'status unknown'))

    def test_app_grants_are_repository_scoped_and_read_only_until_recovery(self):
        for recovery, permission in ((False, 'read'), (True, 'write')):
            with self.subTest(recovery=recovery), app_credentials(), patch('scripts.ranking_alerts.autonomous_scheduler.subprocess.run') as sign, patch('scripts.ranking_alerts.autonomous_scheduler._request') as request:
                sign.return_value.stdout = b'fixture-signature'
                request.return_value = {'token': 'fixture-token', 'expires_at': '2099-01-01T00:00:00Z'}
                client = GitHubActionsClient('owner/repo', '', recovery_enabled=recovery)
                client.authentication_token()
                self.assertEqual({'repositories': ['repo'], 'permissions': {'actions': permission}}, request.call_args.kwargs['payload'])
                self.assertEqual(['-sigopt', 'rsa_padding_mode:pkcs1'], sign.call_args.args[0][-2:])
                self.assertEqual(10, sign.call_args.kwargs['timeout'])
                self.assertTrue(sign.call_args.kwargs['capture_output'])
                if not recovery:
                    request.reset_mock()
                    with self.assertRaises(ValueError):
                        client.dispatch()
                    request.assert_not_called()

    def test_near_expiry_token_is_renewed_at_sixty_second_boundary(self):
        with app_credentials(), patch('scripts.ranking_alerts.autonomous_scheduler.datetime') as clock, patch('scripts.ranking_alerts.autonomous_scheduler.subprocess.run') as sign, patch('scripts.ranking_alerts.autonomous_scheduler._request') as request:
            now = at('2026-10-13T14:00:00Z')
            clock.now.return_value = now
            clock.fromisoformat.side_effect = datetime.fromisoformat
            sign.return_value.stdout = b'fixture-signature'
            request.return_value = {'token': 'fixture-renewed', 'expires_at': '2026-10-13T15:00:00Z'}
            client = GitHubActionsClient('owner/repo', 'fixture-old')
            client.token_expires = now + timedelta(seconds=61)
            self.assertEqual('fixture-old', client.authentication_token())
            request.assert_not_called()
            client.token_expires = now + timedelta(seconds=60)
            self.assertEqual('fixture-renewed', client.authentication_token())
            self.assertEqual(1, request.call_count)

    def test_expired_missing_and_invalid_grants_never_replace_cached_credentials(self):
        grants = ({'token': 'fixture-expired', 'expires_at': '2000-01-01T00:00:00Z'},
                  {'token': '', 'expires_at': '2099-01-01T00:00:00Z'},
                  {'token': None, 'expires_at': '2099-01-01T00:00:00Z'},
                  {'token': 'fixture-token', 'expires_at': 'not-a-time'})
        for grant in grants:
            with self.subTest(grant=grant), app_credentials(), patch('scripts.ranking_alerts.autonomous_scheduler.subprocess.run') as sign, patch('scripts.ranking_alerts.autonomous_scheduler._request', return_value=grant):
                sign.return_value.stdout = b'fixture-signature'
                client = GitHubActionsClient('owner/repo', 'fixture-old')
                client.token_expires = at('2000-01-01T00:00:00Z')
                with self.assertRaises((ValueError, KeyError)):
                    client.authentication_token()
                self.assertEqual('fixture-old', client.token)
                self.assertEqual(at('2000-01-01T00:00:00Z'), client.token_expires)

    def test_unsafe_or_symlinked_key_is_rejected_before_signing(self):
        with app_credentials() as key, patch('scripts.ranking_alerts.autonomous_scheduler.subprocess.run') as sign, patch('scripts.ranking_alerts.autonomous_scheduler._request') as request:
            key.chmod(0o644)
            with self.assertRaises(ValueError):
                GitHubActionsClient('owner/repo', '').authentication_token()
            key.chmod(0o640)
            link = key.with_name('link.pem')
            link.symlink_to(key)
            os.environ['ATP_WATCHDOG_APP_PRIVATE_KEY_PATH'] = str(link)
            with self.assertRaises(ValueError):
                GitHubActionsClient('owner/repo', '').authentication_token()
            sign.assert_not_called()
            request.assert_not_called()

    def test_real_synthetic_rsa_signature_matches_jwt_header(self):
        with app_credentials() as key:
            subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(key)], check=True, capture_output=True, timeout=10)
            public = subprocess.run(['openssl', 'pkey', '-in', str(key), '-pubout'], check=True, capture_output=True, timeout=10).stdout
            with patch('scripts.ranking_alerts.autonomous_scheduler._request', return_value={'token': 'fixture-token', 'expires_at': '2099-01-01T00:00:00Z'}) as request:
                GitHubActionsClient('owner/repo', '').authentication_token()
            jwt = request.call_args.kwargs['token']
            header, claims, signature = jwt.split('.')
            self.assertEqual('RS256', json.loads(base64.urlsafe_b64decode(header + '=' * (-len(header) % 4)))['alg'])
            public_path, signature_path = key.with_name('public.pem'), key.with_name('signature.bin')
            public_path.write_bytes(public)
            signature_path.write_bytes(base64.urlsafe_b64decode(signature + '=' * (-len(signature) % 4)))
            verified = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(public_path), '-signature', str(signature_path)], input=f'{header}.{claims}'.encode(), capture_output=True, timeout=10)
            self.assertEqual(0, verified.returncode)

    def test_app_get_401_refreshes_once_but_dispatch_never_replays(self):
        with app_credentials(), patch('scripts.ranking_alerts.autonomous_scheduler.subprocess.run') as sign, patch('scripts.ranking_alerts.autonomous_scheduler._request') as request:
            sign.return_value.stdout = b'fixture-signature'
            grant = {'token': 'fixture-renewed', 'expires_at': '2099-01-01T00:00:00Z'}
            unauthorized = urllib.error.HTTPError('https://api.example.test', 401, 'fixture-secret', {}, None)
            client = GitHubActionsClient('owner/repo', 'fixture-old', recovery_enabled=True)
            client.token_expires = at('2099-01-01T00:00:00Z')
            request.side_effect = [unauthorized, grant, {'state': 'active'}, {'workflow_runs': []}]
            self.assertEqual(('active', []), client.inspect())
            self.assertEqual(4, request.call_count)
            self.assertEqual('fixture-renewed', client.token)
            request.reset_mock(side_effect=True)
            request.side_effect = unauthorized
            with self.assertRaises(urllib.error.HTTPError):
                client.dispatch()
            self.assertEqual(1, request.call_count)
            self.assertIn('/dispatches', request.call_args.args[0])

    def test_403_429_and_timeout_become_unavailable_without_dispatch_or_secret(self):
        failures = [urllib.error.HTTPError('https://fixture-secret.test', code, 'fixture-secret', {'Retry-After': '1800'}, None) for code in (403, 429)]
        failures.append(TimeoutError('fixture-secret'))
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), patch('scripts.ranking_alerts.autonomous_scheduler._request', side_effect=failure) as request:
                store = WatchdogStore(Path(directory))
                self.addCleanup(store.close)
                client = GitHubActionsClient('owner/repo', 'fixture-token', recovery_enabled=True)
                report = watchdog_cycle(now=at('2026-10-13T14:00:00Z'), client=client, store=store, sender=lambda *_: True, released=True, recovery_enabled=True)
                self.assertEqual(['MONITOR_UNAVAILABLE'], [item['code'] for item in report['incidents']])
                self.assertEqual(0, report['recoveries'])
                self.assertNotIn('fixture-secret', json.dumps(report))
                self.assertEqual(1, request.call_count)
                self.assertEqual(0, store.connection.execute('SELECT count(*) FROM recoveries').fetchone()[0])

    def test_rate_limit_deadline_survives_process_restart_and_skips_get(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), patch('scripts.ranking_alerts.autonomous_scheduler._request') as request, patch('scripts.ranking_alerts.autonomous_scheduler.datetime') as clock:
            now = at('2026-10-13T14:00:00Z')
            clock.now.return_value = now
            clock.fromisoformat.side_effect = datetime.fromisoformat
            request.side_effect = urllib.error.HTTPError('https://fixture.test', 429, 'fixture-secret', {'Retry-After': '1800'}, None)
            store = WatchdogStore(Path(directory))
            watchdog_cycle(now=now, client=GitHubActionsClient('owner/repo', 'fixture-token'), store=store, sender=lambda *_: True, released=True, recovery_enabled=False)
            self.assertEqual('2026-10-13T14:30:00Z', store.connection.execute("SELECT value FROM health WHERE key='api_retry_at'").fetchone()[0])
            store.close()
            request.reset_mock()
            store = WatchdogStore(Path(directory))
            try:
                report = watchdog_cycle(now=now + timedelta(minutes=10), client=GitHubActionsClient('owner/repo', 'fixture-token'), store=store, sender=lambda *_: True, released=True, recovery_enabled=False)
                request.assert_not_called()
                self.assertEqual('MONITOR_UNAVAILABLE', report['incidents'][0]['code'])
                request.side_effect = [{'state': 'active'}, {'workflow_runs': [run(at('2026-10-13T12:17:00Z'))]}]
                report = watchdog_cycle(now=now + timedelta(minutes=30), client=GitHubActionsClient('owner/repo', 'fixture-token'), store=store, sender=lambda *_: True, released=True, recovery_enabled=False)
                self.assertEqual([], report['incidents'])
                self.assertEqual(2, request.call_count)
            finally:
                store.close()

    def test_uncertain_dispatches_consume_two_durable_reservations_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            now = at('2026-10-13T14:00:00Z')
            client = Client()
            client.dispatch = Mock(side_effect=TimeoutError('fixture-secret'))
            for minute in (0, 10, 30, 60):
                store = WatchdogStore(Path(directory))
                try:
                    report = watchdog_cycle(now=now + timedelta(minutes=minute), client=client, store=store, sender=lambda *_: True, released=True, recovery_enabled=True)
                    self.assertNotIn('fixture-secret', json.dumps(report))
                    self.assertLessEqual(store.connection.execute('SELECT count(*) FROM recoveries').fetchone()[0], 2)
                finally:
                    store.close()
            self.assertEqual(2, client.dispatch.call_count)
            store = WatchdogStore(Path(directory))
            try:
                self.assertEqual(['unknown_or_failed', 'unknown_or_failed'], [row[0] for row in store.connection.execute('SELECT result FROM recoveries ORDER BY attempt')])
            finally:
                store.close()

    def test_real_sqlite_lock_fails_closed_without_dispatch_or_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WatchdogStore(Path(directory))
            holder = sqlite3.connect(store.path)
            try:
                store.connection.execute('PRAGMA busy_timeout=1')
                holder.execute('BEGIN IMMEDIATE')
                client, sender = Client(), Mock(return_value=True)
                report = watchdog_cycle(now=at('2026-10-13T14:00:00Z'), client=client, store=store, sender=sender, released=True, recovery_enabled=True)
                self.assertEqual('MONITOR_UNAVAILABLE', report['incidents'][0]['code'])
                self.assertEqual('unknown', report['recovery_state'])
                self.assertEqual(0, client.dispatches)
                sender.assert_not_called()
            finally:
                holder.rollback()
                holder.close()
                store.close()

    def test_database_initialization_failure_is_sanitized(self):
        with patch.dict(os.environ, {'ATP_WATCHDOG_ENABLED': 'true', 'ATP_RANKING_DELIVERY_ENABLED': 'true'}, clear=True), patch('scripts.ranking_alerts.autonomous_scheduler.WatchdogStore', side_effect=sqlite3.OperationalError('fixture-secret path')), patch('scripts.ranking_alerts.autonomous_scheduler.webhook_sender') as sender, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(1, main([]))
        report = json.loads(output.getvalue())
        self.assertEqual('MONITOR_UNAVAILABLE', report['incidents'][0]['code'])
        self.assertNotIn('fixture-secret', output.getvalue())
        sender.assert_not_called()

    def test_disabled_dry_run_never_mints_app_token_or_creates_state(self):
        for disabled in (True, False):
            with self.subTest(disabled=disabled), app_credentials(), tempfile.TemporaryDirectory() as directory, patch('scripts.ranking_alerts.autonomous_scheduler._request') as request, patch('scripts.ranking_alerts.autonomous_scheduler.subprocess.run') as sign, patch('scripts.ranking_alerts.autonomous_scheduler.webhook_sender') as sender, contextlib.redirect_stdout(io.StringIO()) as output:
                os.environ['ATP_WATCHDOG_ENABLED'] = 'false' if disabled else 'true'
                os.environ['ATP_RANKING_DELIVERY_ENABLED'] = 'true'
                os.environ['ATP_WATCHDOG_RECOVERY_ENABLED'] = 'true'
                state = Path(directory) / 'absent'
                main(['--state-dir', str(state)] + ([] if disabled else ['--dry-run']))
                self.assertFalse(state.exists())
                self.assertEqual('MONITOR_UNAVAILABLE', json.loads(output.getvalue())['incidents'][0]['code'])
                request.assert_not_called()
                sign.assert_not_called()
                sender.assert_not_called()

    def test_dry_run_with_supplied_app_token_performs_only_gets(self):
        with app_credentials(), tempfile.TemporaryDirectory() as directory, patch('scripts.ranking_alerts.autonomous_scheduler._request', return_value={'state': 'disabled_manually'}) as request, patch('scripts.ranking_alerts.autonomous_scheduler.subprocess.run') as sign, contextlib.redirect_stdout(io.StringIO()):
            os.environ['ATP_WATCHDOG_GITHUB_TOKEN'] = 'fixture-read-token'
            state = Path(directory) / 'absent'
            main(['--dry-run', '--state-dir', str(state)])
            self.assertEqual(1, request.call_count)
            self.assertIsNone(request.call_args.kwargs['payload'])
            self.assertFalse(state.exists())
            sign.assert_not_called()

    def test_truthy_non_boolean_sender_ack_remains_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WatchdogStore(Path(directory))
            try:
                store.enqueue('fixture-event', 'fixture-status')
                self.assertEqual(0, store.flush(lambda *_: {'accepted': True}, at('2026-10-13T14:00:00Z')))
                self.assertEqual('pending', store.connection.execute('SELECT status FROM alerts').fetchone()[0])
            finally:
                store.close()

    def test_two_real_git_clones_share_external_claim_without_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            origin = root / 'origin'
            subprocess.run(['git', 'init', '-q', str(origin)], check=True)
            (origin / 'marker').write_text('fixture')
            subprocess.run(['git', '-C', str(origin), 'add', 'marker'], check=True)
            subprocess.run(['git', '-C', str(origin), '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.test', 'commit', '-qm', 'fixture'], check=True)
            processes = []
            # Initialize schema before racing hosts' local processes.
            WatchdogStore(root / 'state').close()
            for i in range(2):
                clone = root / f'clone-{i}'
                subprocess.run(['git', 'clone', '-q', str(origin), str(clone)], check=True)
                process = multiprocessing.Process(target=concurrent_recovery, args=(clone, root / 'state', root / f'output-{i}.json'))
                process.start()
                processes.append(process)
            for process in processes:
                process.join(10)
                self.assertEqual(0, process.exitcode)
            reports = [json.loads((root / f'output-{i}.json').read_text()) for i in range(2)]
            self.assertEqual(1, sum(report['recoveries'] for report in reports))
            self.assertEqual(1, sum(report['alerts_accepted'] for report in reports))
