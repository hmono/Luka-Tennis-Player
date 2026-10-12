from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import update_rankings
from ranking_alerts.domain import DisciplineRanking, RankingObservation, RankingsData, build_snapshot
from ranking_alerts.incidents import load_incidents, pending_incidents
from ranking_alerts.providers import DeliveryReceipt
from ranking_alerts.source import RawDisciplineRanking, RawRankingObservation, RankingSourceError
from ranking_alerts.storage import load_alert_state, load_rankings, save_rankings


class Source:
    name = "itf"

    def __init__(self, edition="2026-09-28", error=None):
        self.edition, self.error = edition, error

    def fetch(self):
        if self.error:
            raise RankingSourceError(self.error)
        return RawRankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
            ranking_date=self.edition,
            singles=RawDisciplineRanking(status="ranked", rank=2250, points=None),
            doubles=RawDisciplineRanking(status="ranked", rank=1417, points=None))


class MockProvider:
    name = "callmebot"
    last_attempt_count = 1

    def __init__(self):
        self.messages = []
        self.accepted_at = "2026-10-08T15:01:00Z"

    def send(self, *, message, event_id):
        self.messages.append((message, event_id))
        return DeliveryReceipt(provider=self.name, accepted_at=self.accepted_at, http_status=200)


class SprintIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.rankings, self.state, self.incidents = root / "rankings.json", root / "state.json", root / "incidents.json"
        observation = RankingObservation(atp_id="B0UF", name="Luka Bojicic Ono", source="itf",
            ranking_date="2026-09-28",
            singles=DisciplineRanking(rank=2250, points=None, career_high_rank=1827, career_high_date="2025-12-01"),
            doubles=DisciplineRanking(rank=1417, points=None, career_high_rank=1407, career_high_date="2026-06-22"))
        save_rankings(self.rankings, RankingsData(snapshots=(build_snapshot(observation, "2026-09-29T12:00:00Z"),)))
        self.state.write_text('{"schema_version":1,"outbox":[]}\n')
        self.original_rankings, self.original_state = self.rankings.read_bytes(), self.state.read_bytes()
        self.provider = MockProvider()

    def main(self, command, instant, source=Source(), enabled=False):
        args = [command, "--provider" if command == "deliver" else "--source", "callmebot" if command == "deliver" else "itf",
                "--rankings-path", str(self.rankings), "--state-path", str(self.state), "--incidents-path", str(self.incidents)]
        output, errors = StringIO(), StringIO()
        with patch.object(update_rankings, "_selected_source", return_value=source), \
             patch.object(update_rankings.CallMeBotProvider, "from_env", return_value=self.provider) as factory, \
             patch.dict("os.environ", {"ATP_RANKING_DELIVERY_ENABLED": "true" if enabled else "false"}), \
             redirect_stdout(output), redirect_stderr(errors):
            result = update_rankings.main(args, clock=lambda: datetime.fromisoformat(instant.replace("Z", "+00:00")))
        return result, output.getvalue(), errors.getvalue(), factory.call_count

    def test_stale_dry_run_has_no_persistence_or_provider_construction(self):
        code, output, errors, calls = self.main("dry-run", "2026-10-08T15:00:00Z")
        self.assertEqual(0, code)
        self.assertIn("incident=would_create", output)
        self.assertEqual(0, calls)
        self.assertFalse(self.incidents.exists())
        self.assertEqual(self.original_rankings, self.rankings.read_bytes())
        self.assertEqual(self.original_state, self.state.read_bytes())

    def test_boundary_multiple_crons_and_stale_recovery_generate_one_intention_each(self):
        self.assertEqual(0, self.main("collect", "2026-10-08T14:59:59Z")[0])
        self.assertFalse(self.incidents.exists())
        self.assertEqual(0, self.main("collect", "2026-10-08T15:00:00Z")[0])
        ledger_bytes = self.incidents.read_bytes()
        self.assertEqual(0, self.main("collect", "2026-10-09T12:00:00Z")[0])
        self.assertEqual(ledger_bytes, self.incidents.read_bytes())
        self.assertEqual(self.original_rankings, self.rankings.read_bytes())
        self.assertEqual(self.original_state, self.state.read_bytes())
        self.assertEqual(0, self.main("deliver", "2026-10-08T15:01:00Z", enabled=True)[0])
        self.assertEqual(0, self.main("deliver", "2026-10-09T12:00:00Z", enabled=True)[0])
        self.assertEqual(1, len(self.provider.messages))
        self.assertIn("RANKING_STALE", self.provider.messages[0][0])
        self.assertEqual(0, self.main("collect", "2026-10-09T12:00:00Z", Source("2026-10-05"))[0])
        self.assertEqual("recovered", load_incidents(self.incidents).events[-1]["kind"])
        self.assertEqual("2026-10-05", load_incidents(self.incidents).events[-1]["recovery_date"])
        self.provider.accepted_at = "2026-10-09T12:01:00Z"
        self.assertEqual(0, self.main("deliver", "2026-10-09T12:01:00Z", enabled=True)[0])
        self.assertEqual(0, self.main("collect", "2026-10-09T12:02:00Z", Source("2026-10-05"))[0])
        self.assertEqual(0, self.main("deliver", "2026-10-09T12:03:00Z", enabled=True)[0])
        self.assertEqual(2, len(self.provider.messages))
        self.assertIn("ATP Ranking — 2026-10-05", self.provider.messages[1][0])
        self.assertEqual((), pending_incidents(load_incidents(self.incidents)))

    def test_source_error_never_creates_incident_or_changes_valid_state(self):
        code, _, error, calls = self.main("collect", "2026-10-08T15:00:00Z", Source(error="ranking_source_blocked"))
        self.assertEqual(1, code)
        self.assertIn("error=ranking_source_blocked", error)
        self.assertEqual(0, calls)
        self.assertFalse(self.incidents.exists())
        self.assertEqual(self.original_rankings, self.rankings.read_bytes())
        self.assertEqual(self.original_state, self.state.read_bytes())

    def test_delivery_release_guard_never_constructs_provider_or_mutates_intent(self):
        self.assertEqual(0, self.main("collect", "2026-10-08T15:00:00Z")[0])
        ledger_bytes = self.incidents.read_bytes()
        code, _, error, calls = self.main("deliver", "2026-10-08T15:01:00Z", enabled=False)
        self.assertEqual(1, code)
        self.assertIn("ranking_delivery_disabled", error)
        self.assertEqual(0, calls)
        self.assertEqual(ledger_bytes, self.incidents.read_bytes())


if __name__ == "__main__":
    unittest.main()
