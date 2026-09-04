from __future__ import annotations

import io
import json
import unittest
import urllib.error
import urllib.parse

from scripts.probe_api_tennis import API_KEY_ENV, MAX_RESPONSE_BYTES, main, probe


class _Response:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, _: int) -> bytes:
        return self.body


class ApiTennisProbeTests(unittest.TestCase):
    def test_missing_key_fails_before_network_and_never_echoes_environment_value(self) -> None:
        output = io.StringIO()
        network_called = False

        def opener(_: object, *, timeout: float) -> _Response:
            nonlocal network_called
            network_called = True
            return _Response(b"{}")

        exit_code, lines = probe(api_key="", opener=opener)
        result = main([], environ={}, output=output)

        self.assertEqual(2, exit_code)
        self.assertEqual(2, result)
        self.assertFalse(network_called)
        self.assertIn("detail=ranking_source_authentication", "\n".join(lines))
        self.assertIn("detail=ranking_source_authentication", output.getvalue())
        self.assertNotIn(API_KEY_ENV, output.getvalue())

    def test_success_uses_documented_query_and_stays_pending(self) -> None:
        secret = "trial-key-never-print-this"
        captured: list[str] = []
        body = json.dumps(
            {
                "success": 1,
                "result": [
                    {"place": 2101, "player": "Luka Bojicic Ono", "api_key": secret}
                ],
            }
        ).encode()

        def opener(request: object, *, timeout: float) -> _Response:
            captured.append(request.full_url)  # type: ignore[attr-defined]
            self.assertEqual(20.0, timeout)
            return _Response(body)

        exit_code, lines = probe(api_key=secret, opener=opener)
        rendered = "\n".join(lines)

        self.assertEqual(0, exit_code)
        self.assertIn(secret, captured[0])
        self.assertNotIn(secret, rendered)
        self.assertNotIn("Luka Bojicic Ono", rendered)
        self.assertNotIn("api_key", rendered)
        parsed = urllib.parse.urlparse(captured[0])
        self.assertEqual("api.api-tennis.com", parsed.hostname)
        self.assertEqual("/tennis/", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["get_standings"], query["method"])
        self.assertEqual(["ATP"], query["event_type"])
        self.assertNotIn("player_name", query)
        self.assertIn("evidence_candidate_name_match=true", rendered)
        self.assertIn("gate_doubles_individual=pending_manual_review", rendered)
        self.assertTrue(rendered.endswith("decision=pending_manual_review"))

    def test_endpoint_override_is_rejected_before_network(self) -> None:
        secret = "trial-key-never-print-this"
        network_called = False

        def opener(_: object, *, timeout: float) -> _Response:
            nonlocal network_called
            network_called = True
            return _Response(b"{}")

        exit_code, lines = probe(
            api_key=secret,
            endpoint="https://attacker.invalid/collect",
            opener=opener,
        )
        rendered = "\n".join(lines)

        self.assertEqual(2, exit_code)
        self.assertFalse(network_called)
        self.assertIn("detail=ranking_source_incomplete", rendered)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("attacker.invalid", rendered)

    def test_missing_candidate_is_no_go_without_exposing_payload(self) -> None:
        payload = {
            "success": 1,
            "result": [{"player": "Different Player"}],
            "metadata": {"query": "Luka Bojicic Ono"},
        }

        exit_code, lines = probe(
            api_key="trial-secret",
            opener=lambda *_args, **_kwargs: _Response(json.dumps(payload).encode()),
        )
        rendered = "\n".join(lines)

        self.assertEqual(1, exit_code)
        self.assertIn("evidence_candidate_name_match=false", rendered)
        self.assertNotIn("Different Player", rendered)
        self.assertNotIn("Luka Bojicic Ono", rendered)
        self.assertTrue(rendered.endswith("decision=no-go"))

    def test_invalid_standings_schema_is_no_go(self) -> None:
        invalid_payloads = (
            [],
            {"success": 0, "result": []},
            {"success": True, "result": []},
            {"success": 1, "result": {}},
            {"success": 1, "result": ["Luka Bojicic Ono"]},
            {"success": 1, "result": [{"name": "Luka Bojicic Ono"}]},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                exit_code, lines = probe(
                    api_key="trial-secret",
                    opener=lambda *_args, **_kwargs: _Response(json.dumps(payload).encode()),
                )

                self.assertEqual(1, exit_code)
                self.assertIn("detail=ranking_source_schema_changed", lines)
                self.assertEqual("decision=no-go", lines[-1])

    def test_oversized_response_is_rejected_before_json_parsing(self) -> None:
        exit_code, lines = probe(
            api_key="trial-secret",
            opener=lambda *_args, **_kwargs: _Response(b"x" * (MAX_RESPONSE_BYTES + 1)),
        )

        self.assertEqual(1, exit_code)
        self.assertIn("detail=ranking_source_coverage_truncated", lines)
        self.assertIn("evidence_response_within_limit=false", lines)
        self.assertEqual("decision=no-go", lines[-1])

    def test_http_failures_are_categorized_without_url_or_secret(self) -> None:
        secret = "do-not-leak"
        expected_codes = {
            401: "ranking_source_authentication",
            403: "ranking_source_blocked",
            429: "ranking_source_rate_limited",
            500: "ranking_source_incomplete",
        }
        for status, expected_code in expected_codes.items():
            with self.subTest(status=status):

                def opener(_: object, *, timeout: float) -> _Response:
                    raise urllib.error.HTTPError(
                        url=f"https://example.test/?APIkey={secret}",
                        code=status,
                        msg="provider failure",
                        hdrs=None,
                        fp=None,
                    )

                exit_code, lines = probe(api_key=secret, opener=opener)
                rendered = "\n".join(lines)

                self.assertEqual(1, exit_code)
                self.assertIn(f"detail={expected_code}", rendered)
                self.assertNotIn(secret, rendered)
                self.assertNotIn("example.test", rendered)
                self.assertEqual("decision=no-go", lines[-1])

    def test_timeout_is_categorized_without_exposing_secret(self) -> None:
        secret = "timeout-secret"

        def opener(_: object, *, timeout: float) -> _Response:
            raise TimeoutError(secret)

        exit_code, lines = probe(api_key=secret, opener=opener)
        rendered = "\n".join(lines)

        self.assertEqual(1, exit_code)
        self.assertIn("detail=ranking_source_timeout", rendered)
        self.assertNotIn(secret, rendered)
        self.assertEqual("decision=no-go", lines[-1])

    def test_invalid_json_is_categorized_without_exposing_body(self) -> None:
        sensitive_body = "not-json-provider-data"
        exit_code, lines = probe(
            api_key="trial-secret",
            opener=lambda *_args, **_kwargs: _Response(sensitive_body.encode()),
        )
        rendered = "\n".join(lines)

        self.assertEqual(1, exit_code)
        self.assertIn("detail=ranking_source_schema_changed", rendered)
        self.assertIn("evidence_response_within_limit=true", rendered)
        self.assertNotIn(sensitive_body, rendered)
        self.assertEqual("decision=no-go", lines[-1])


if __name__ == "__main__":
    unittest.main()
