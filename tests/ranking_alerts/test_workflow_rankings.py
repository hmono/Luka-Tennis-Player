from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "update_rankings.yml"


class RankingsWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.steps = cls.text.split("- name:")

    def test_runs_weekly_after_the_monday_atp_publication_on_github_runners(self) -> None:
        self.assertIn("schedule:", self.text)
        self.assertIn("cron: '0 12 * * 2-5'", self.text)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("runs-on: ubuntu-latest", self.text)
        self.assertNotIn("self-hosted", self.text)

    def test_uses_the_itf_source_and_persists_before_delivering(self) -> None:
        self.assertIn("update_rankings.py collect --source itf", self.text)
        self.assertIn("update_rankings.py deliver --provider callmebot", self.text)
        self.assertLess(self.text.index("collect --source itf"), self.text.index("deliver --provider"))
        self.assertLess(self.text.index("git push"), self.text.index("deliver --provider"))
        self.assertIn("contents: write", self.text)
        self.assertIn("group: repository-data-writer-main", self.text)

    def test_notification_secrets_are_scoped_to_the_delivery_step_only(self) -> None:
        holders = [step for step in self.steps if "CALLMEBOT_" in step]
        self.assertEqual(1, len(holders))
        self.assertIn("deliver --provider callmebot", holders[0])
        for step in self.steps:
            if "deliver --provider" not in step:
                self.assertNotIn("secrets.", step)

    def test_no_pdf_or_api_tennis_leftovers(self) -> None:
        self.assertNotIn("probe_atp_pdfs", self.text)
        self.assertNotIn("API_TENNIS_API_KEY", self.text)

    def test_dispatch_defaults_to_dry_run_and_release_gates_all_writers(self) -> None:
        self.assertIn("default: dry-run", self.text)
        writers = [step for step in self.steps if any(token in step for token in ("collect --source", "git add", "deliver --provider"))]
        self.assertEqual(4, len(writers))
        for step in writers:
            self.assertIn("vars.ATP_RANKING_DELIVERY_ENABLED == 'true'", step)
            self.assertIn("inputs.mode != 'dry-run'", step)
        self.assertIn("github.event_name == 'schedule' && vars.ATP_RANKING_DELIVERY_ENABLED != 'true'", self.text)
        self.assertIn("Require explicit release for collect-and-deliver", self.text)

    def test_scheduler_timing_uses_run_metadata_before_collection(self) -> None:
        self.assertIn("actions: read", self.text)
        self.assertIn("run_started_at: .run_started_at", self.text)
        self.assertIn("created_at: .created_at", self.text)
        self.assertIn("telemetry --event-name", self.text)
        self.assertLess(self.text.index("telemetry --event-name"), self.text.index("collect --source"))


if __name__ == "__main__":
    unittest.main()
