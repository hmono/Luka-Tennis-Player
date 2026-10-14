from __future__ import annotations

import io
import json
import socket
import unittest
import urllib.error
import urllib.parse
from typing import Any

from scripts.probe_matchstat import API_HOST, API_KEY_ENV, main, probe


RANKING_DATE = "2026-09-07T00:00:00Z"


class _Response:
    def __init__(self, payload: Any, *, status: int = 200, headers: Any = None) -> None:
        self.body = json.dumps(payload).encode("utf-8")
        self.status = status
        self.headers = headers

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, _: int) -> bytes:
        return self.body


def _ranking_row(*, discipline: str) -> dict[str, Any]:
    return {
        "position": 2162 if discipline == "singles" else 1784,
        "pts": 1 if discipline == "singles" else 3,
        "player": {"name": "Luka Bojicic Ono", "countryAcr": "BRA"},
    }


class MatchstatProbeTests(unittest.TestCase):
    def test_missing_key_fails_before_network(self) -> None:
        network_called = False

        def opener(_: object, *, timeout: float) -> _Response:
            nonlocal network_called
            network_called = True
            return _Response({})

        exit_code, lines = probe(api_key="", opener=opener)
        output = io.StringIO()
        cli_exit = main([], environ={}, output=output)

        self.assertEqual(2, exit_code)
        self.assertEqual(2, cli_exit)
        self.assertFalse(network_called)
        self.assertIn("detail=ranking_source_authentication", lines)
        self.assertNotIn(API_KEY_ENV, output.getvalue())
        self.assertTrue(output.getvalue().rstrip().endswith("decision=no-go"))

    def test_success_requests_filters_and_both_disciplines_without_leaking_key(self) -> None:
        secret = "rapidapi-trial-secret-never-print"
        requests: list[tuple[str, dict[str, list[str]], dict[str, str]]] = []

        def opener(request: object, *, timeout: float) -> _Response:
            parsed = urllib.parse.urlparse(request.full_url)  # type: ignore[attr-defined]
            query = urllib.parse.parse_qs(parsed.query)
            headers = dict(request.header_items())  # type: ignore[attr-defined]
            requests.append((parsed.path, query, headers))
            self.assertEqual(20.0, timeout)
            if parsed.path.endswith("/filters"):
                return _Response({"date": [RANKING_DATE]})
            discipline = query["group"][0]
            return _Response([_ranking_row(discipline=discipline)] if query["page"] == ["1"] else [])

        exit_code, lines = probe(api_key=secret, opener=opener)
        rendered = "\n".join(lines)

        self.assertEqual(0, exit_code)
        self.assertEqual(5, len(requests))
        self.assertEqual("/tennis/v2/ranking/atp/filters", requests[0][0])
        self.assertEqual({}, requests[0][1])
        ranking_requests = requests[1:]
        self.assertEqual(["singles", "singles", "doubles", "doubles"], [item[1]["group"][0] for item in ranking_requests])
        for _, query, headers in ranking_requests:
            self.assertEqual(["07.09.2026"], query["date"])
            self.assertEqual(["BRA"], query["countryAcr"])
            self.assertEqual(["100"], query["limit"])
            self.assertNotIn(secret, urllib.parse.urlencode(query, doseq=True))
            self.assertEqual(API_HOST, headers["X-rapidapi-host"])
            self.assertEqual(secret, headers["X-rapidapi-key"])
        self.assertNotIn(secret, rendered)
        self.assertIn("ranking_date=2026-09-07", rendered)
        self.assertIn("singles_rank=2162", rendered)
        self.assertIn("singles_points=1", rendered)
        self.assertIn("doubles_rank=1784", rendered)
        self.assertIn("doubles_points=3", rendered)
        self.assertIn("gate_identity=pending_manual_review", rendered)
        self.assertIn("gate_atp_id_mapping=pending_manual_review", rendered)
        self.assertTrue(rendered.endswith("decision=pending_manual_review"))

    def test_invalid_filters_or_ranking_schema_is_no_go(self) -> None:
        invalid_filters = (
            ({}, "ranking_source_schema_changed"),
            ({"date": []}, "ranking_source_incomplete"),
            ({"date": "2026-09-07"}, "ranking_source_schema_changed"),
            ({"date": [17]}, "ranking_source_schema_changed"),
            ({"date": ["invalid"]}, "ranking_source_schema_changed"),
        )
        for payload, detail in invalid_filters:
            with self.subTest(filters=payload):
                exit_code, lines = probe(api_key="secret", opener=lambda *_args, **_kwargs: _Response(payload))
                self.assertEqual(1, exit_code)
                self.assertIn(f"detail={detail}", lines)
                self.assertEqual("decision=no-go", lines[-1])

        responses: list[Any] = [
            {"date": [RANKING_DATE]},
            {"unexpected": "object-instead-of-ranking-list"},
        ]

        def opener(*_args: object, **_kwargs: object) -> _Response:
            return _Response(responses.pop(0))

        exit_code, lines = probe(api_key="secret", opener=opener)
        self.assertEqual(1, exit_code)
        self.assertIn("detail=ranking_source_schema_changed", lines)
        self.assertEqual("decision=no-go", lines[-1])

    def test_identity_cannot_be_verified_when_country_disagrees(self) -> None:
        def opener(request: object, *, timeout: float) -> _Response:
            parsed = urllib.parse.urlparse(request.full_url)  # type: ignore[attr-defined]
            if parsed.path.endswith("/filters"):
                return _Response({"date": [RANKING_DATE]})
            query = urllib.parse.parse_qs(parsed.query)
            if query["page"] == ["2"]:
                return _Response([])
            row = _ranking_row(discipline=query["group"][0])
            row["player"]["countryAcr"] = "USA"
            return _Response([row])

        exit_code, lines = probe(api_key="secret", opener=opener)

        self.assertEqual(1, exit_code)
        self.assertIn("detail=ranking_source_identity_mismatch", lines)
        self.assertIn("gate_identity=pending_manual_review", lines)
        self.assertEqual("decision=no-go", lines[-1])

    def test_http_401_and_403_fail_closed_without_retry_or_secret_leak(self) -> None:
        secret = "http-secret"
        for status, detail in ((401, "ranking_source_authentication"), (403, "ranking_source_blocked")):
            with self.subTest(status=status):
                calls = 0

                def opener(_: object, *, timeout: float) -> _Response:
                    nonlocal calls
                    calls += 1
                    raise urllib.error.HTTPError(
                        url=f"https://provider.invalid/?secret={secret}",
                        code=status,
                        msg=secret,
                        hdrs=None,
                        fp=None,
                    )

                exit_code, lines = probe(api_key=secret, opener=opener)
                rendered = "\n".join(lines)
                self.assertEqual(1, exit_code)
                self.assertEqual(1, calls)
                self.assertIn(f"detail={detail}", rendered)
                self.assertNotIn(secret, rendered)
                self.assertEqual("decision=no-go", lines[-1])

    def test_http_429_honors_retry_after_then_fails_closed(self) -> None:
        calls = 0
        sleeps: list[float] = []

        def opener(_: object, *, timeout: float) -> _Response:
            nonlocal calls
            calls += 1
            raise urllib.error.HTTPError(
                url="https://provider.invalid/",
                code=429,
                msg="rate limited",
                hdrs={"Retry-After": "7"},
                fp=None,
            )

        exit_code, lines = probe(api_key="secret", opener=opener, sleeper=sleeps.append)

        self.assertEqual(1, exit_code)
        self.assertEqual(3, calls)
        self.assertEqual([7.0, 7.0], sleeps)
        self.assertIn("detail=ranking_source_rate_limited", lines)
        self.assertEqual("decision=no-go", lines[-1])

    def test_timeout_retries_then_fails_closed_without_leaking_exception(self) -> None:
        secret = "timeout-secret"
        calls = 0
        sleeps: list[float] = []

        def opener(_: object, *, timeout: float) -> _Response:
            nonlocal calls
            calls += 1
            raise socket.timeout(secret)

        exit_code, lines = probe(api_key=secret, opener=opener, sleeper=sleeps.append)
        rendered = "\n".join(lines)

        self.assertEqual(1, exit_code)
        self.assertEqual(3, calls)
        self.assertEqual([1.0, 2.0], sleeps)
        self.assertIn("detail=ranking_source_timeout", rendered)
        self.assertNotIn(secret, rendered)
        self.assertEqual("decision=no-go", lines[-1])


if __name__ == "__main__":
    unittest.main()
