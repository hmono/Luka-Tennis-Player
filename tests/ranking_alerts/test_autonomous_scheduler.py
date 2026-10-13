from __future__ import annotations

import json
import base64
import multiprocessing
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts.ranking_alerts.autonomous_scheduler import (
    GitHubActionsClient, WatchdogStore, assess_runs, iso, main, poll_slots,
    send_operational_alert, watchdog_cycle, weekly_period, webhook_sender,
)


def at(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


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
        with patch.dict(os.environ, {"ATP_WATCHDOG_APP_ID": "123", "ATP_WATCHDOG_APP_INSTALLATION_ID": "456", "ATP_WATCHDOG_APP_PRIVATE_KEY_PATH": "/protected/key.pem"}, clear=True), patch('scripts.ranking_alerts.autonomous_scheduler.subprocess.run') as sign, patch('scripts.ranking_alerts.autonomous_scheduler._request') as request:
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
