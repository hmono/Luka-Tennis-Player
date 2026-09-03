from __future__ import annotations

import io
import unittest
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from scripts.ranking_alerts.providers import (
    CallMeBotProvider,
    ConfigurationError,
    DeliveryError,
    DryRunProvider,
)


PHONE = "+5511999999999"
API_KEY = "key with &=? reserved"
ACCEPTED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status: int = 200, headers: dict[str, str] | None = None):
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, *args, **kwargs) -> bytes:
        return b"provider response deliberately ignored"


def http_error(status: int, headers: dict[str, str] | None = None) -> HTTPError:
    return HTTPError(
        url="https://provider.invalid/redacted",
        code=status,
        msg="simulated provider failure",
        hdrs=headers or {},
        fp=io.BytesIO(b"body must never be persisted"),
    )


class SequenceOpener:
    def __init__(self, *actions):
        self.actions = list(actions)
        self.requests = []
        self.timeouts = []

    def __call__(self, request, *, timeout):
        self.requests.append(request)
        self.timeouts.append(timeout)
        action = self.actions.pop(0)
        if isinstance(action, BaseException):
            raise action
        return action


def provider(opener, **overrides) -> CallMeBotProvider:
    options = {
        "phone": PHONE,
        "api_key": API_KEY,
        "opener": opener,
        "sleep": lambda _seconds: None,
        "random_uniform": lambda _start, end: end,
        "now": lambda: ACCEPTED_AT,
    }
    options.update(overrides)
    return CallMeBotProvider(**options)


class ConfigurationTests(unittest.TestCase):
    def test_rejects_invalid_phone_without_exposing_configuration(self) -> None:
        for invalid in ("", "5511999999999", "+012345678", "+5511"):
            with self.subTest(phone=invalid):
                with self.assertRaises(ConfigurationError) as raised:
                    CallMeBotProvider(phone=invalid, api_key=API_KEY)
                self.assertNotIn(API_KEY, str(raised.exception))

    def test_rejects_blank_api_key(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            CallMeBotProvider(phone=PHONE, api_key="   ")

        self.assertNotIn(PHONE, str(raised.exception))


class CallMeBotProviderTests(unittest.TestCase):
    def test_url_encodes_query_parameters_and_accepts_any_2xx(self) -> None:
        opener = SequenceOpener(FakeResponse(status=204))
        client = provider(opener)
        message = "ATP Ranking — Singles: #1.973 (+6) & 5 pts"

        receipt = client.send(message=message, event_id="sha256:" + "a" * 64)

        url = opener.requests[0].get_full_url()
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual("https", parsed.scheme)
        self.assertEqual("api.callmebot.com", parsed.netloc)
        self.assertEqual("/whatsapp.php", parsed.path)
        self.assertEqual([PHONE], query["phone"])
        self.assertEqual([message], query["text"])
        self.assertEqual([API_KEY], query["apikey"])
        self.assertEqual("callmebot", receipt.provider)
        self.assertEqual(204, receipt.http_status)
        self.assertEqual("2026-09-01T12:00:00Z", receipt.accepted_at)
        self.assertEqual([15.0], opener.timeouts)
        self.assertEqual(1, client.last_attempt_count)

    def test_429_respects_bounded_retry_after_then_succeeds(self) -> None:
        sleeps: list[float] = []
        opener = SequenceOpener(
            http_error(429, {"Retry-After": "240"}),
            FakeResponse(status=200),
        )
        client = provider(opener, sleep=sleeps.append)

        client.send(message="ranking changed", event_id="sha256:" + "b" * 64)

        self.assertEqual([120.0], sleeps)
        self.assertEqual(2, client.last_attempt_count)

    def test_5xx_retries_with_backoff_and_stops_after_four_attempts(self) -> None:
        sleeps: list[float] = []
        opener = SequenceOpener(*(http_error(500) for _ in range(4)))
        client = provider(opener, sleep=sleeps.append)

        with self.assertRaises(DeliveryError) as raised:
            client.send(message="ranking changed", event_id="sha256:" + "c" * 64)

        self.assertEqual("http_500", raised.exception.code)
        self.assertEqual(4, raised.exception.attempts)
        self.assertEqual(4, client.last_attempt_count)
        self.assertEqual(3, len(sleeps))

    def test_permanent_401_does_not_retry(self) -> None:
        opener = SequenceOpener(http_error(401))
        client = provider(opener)

        with self.assertRaises(DeliveryError) as raised:
            client.send(message="ranking changed", event_id="sha256:" + "d" * 64)

        self.assertEqual("http_401", raised.exception.code)
        self.assertEqual(1, raised.exception.attempts)
        self.assertEqual(1, len(opener.requests))

    def test_timeout_is_retryable_and_redacted(self) -> None:
        opener = SequenceOpener(*(TimeoutError("timed out after signed URL") for _ in range(4)))
        client = provider(opener)

        with self.assertRaises(DeliveryError) as raised:
            client.send(message="ranking changed", event_id="sha256:" + "e" * 64)

        error = raised.exception
        self.assertEqual("transport_timeout", error.code)
        self.assertEqual(4, error.attempts)
        self.assertNotIn(PHONE, str(error))
        self.assertNotIn(API_KEY, str(error))
        self.assertNotIn("signed URL", str(error))

    def test_http_error_body_and_signed_url_are_not_exposed(self) -> None:
        secret_error = HTTPError(
            url=f"https://api.callmebot.com/whatsapp.php?phone={PHONE}&apikey={API_KEY}",
            code=403,
            msg="body contains provider detail",
            hdrs={},
            fp=io.BytesIO(b"sensitive response body"),
        )
        client = provider(SequenceOpener(secret_error))

        with self.assertRaises(DeliveryError) as raised:
            client.send(message="ranking changed", event_id="sha256:" + "f" * 64)

        rendered = str(raised.exception)
        self.assertEqual("http_403", raised.exception.code)
        self.assertNotIn(PHONE, rendered)
        self.assertNotIn(API_KEY, rendered)
        self.assertNotIn("sensitive response body", rendered)


class DryRunProviderTests(unittest.TestCase):
    def test_returns_in_memory_receipt_without_network(self) -> None:
        client = DryRunProvider(now=lambda: ACCEPTED_AT)

        receipt = client.send(message="candidate", event_id="sha256:" + "1" * 64)

        self.assertEqual("dry-run", receipt.provider)
        self.assertEqual("2026-09-01T12:00:00Z", receipt.accepted_at)
        self.assertIsNone(receipt.http_status)


if __name__ == "__main__":
    unittest.main()
