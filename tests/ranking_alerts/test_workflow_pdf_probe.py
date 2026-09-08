from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "update_rankings.yml"


class PdfQualificationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_is_manual_and_has_no_schedule(self) -> None:
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.text)
        self.assertNotIn("cron:", self.text)

    def test_uses_dedicated_self_hosted_macos_runner(self) -> None:
        self.assertIn("runs-on: [self-hosted, macOS, atp-ranking]", self.text)

    def test_is_read_only_and_does_not_load_notification_secrets(self) -> None:
        self.assertIn("contents: read", self.text)
        self.assertNotIn("contents: write", self.text)
        self.assertNotIn("CALLMEBOT_", self.text)
        self.assertNotIn("API_TENNIS_API_KEY", self.text)

    def test_only_runs_the_nonpersistent_probe(self) -> None:
        self.assertIn("python scripts/probe_atp_pdfs.py", self.text)
        self.assertNotIn("update_rankings.py collect", self.text)
        self.assertNotIn("update_rankings.py deliver", self.text)
        self.assertNotIn("git push", self.text)


if __name__ == "__main__":
    unittest.main()
