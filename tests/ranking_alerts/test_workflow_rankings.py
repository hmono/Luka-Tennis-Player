from __future__ import annotations
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / '.github/workflows/update_rankings.yml'


class RankingsWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text()
        cls.steps = cls.text.split('- name:')

    def test_daily_intraday_polling_and_current_branch_dry_run(self):
        self.assertIn("cron: '17 12,18 * * *'", self.text)
        self.assertIn('workflow_dispatch:', self.text)
        self.assertIn('default: dry-run', self.text)
        self.assertIn('ref: ${{ github.ref_name }}', self.text)
        self.assertIn('python scripts/autonomous_rankings.py run --dry-run', self.text)
        self.assertIn('runs-on: ubuntu-latest', self.text)
        self.assertNotIn('self-hosted', self.text)

    def test_release_flag_and_main_guard_cover_entire_production_cycle(self):
        production = next(step for step in self.steps if 'python scripts/autonomous_rankings.py run\n' in step)
        self.assertIn("vars.ATP_RANKING_DELIVERY_ENABLED == 'true'", production)
        self.assertIn("inputs.mode != 'dry-run'", production)
        self.assertIn("github.ref == 'refs/heads/main'", production)
        self.assertIn('Require explicit release for collect-and-deliver', self.text)
        self.assertIn("github.event_name == 'schedule' && vars.ATP_RANKING_DELIVERY_ENABLED != 'true'", self.text)
        self.assertNotIn('continue-on-error', self.text)

    def test_notification_secrets_only_exist_in_production_cycle(self):
        holders = [step for step in self.steps if 'secrets.' in step]
        self.assertEqual(1, len(holders))
        self.assertIn('python scripts/autonomous_rankings.py run\n', holders[0])
        self.assertIn('CALLMEBOT_API_KEY', holders[0])
        self.assertIn('ATP_OPS_WEBHOOK_URL', holders[0])

    def test_shared_writer_concurrency_and_timing(self):
        self.assertIn('contents: write', self.text)
        self.assertIn('actions: read', self.text)
        self.assertIn('group: repository-data-writer-main', self.text)
        self.assertIn('cancel-in-progress: false', self.text)
        self.assertIn('run_started_at: .run_started_at', self.text)
        self.assertIn('created_at: .created_at', self.text)
        self.assertLess(self.text.index('telemetry --event-name'), self.text.index('autonomous_rankings.py run'))
        self.assertIn('run-name: ATP rankings', self.text)
        self.assertNotIn('probe_atp_pdfs', self.text)
        self.assertNotIn('API_TENNIS_API_KEY', self.text)
