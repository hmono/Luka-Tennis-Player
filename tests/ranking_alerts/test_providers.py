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
    def __init__(self, status: int = 200, headers: dict[str, str] | None = None, body: bytes = b"<b>Message queued.</b> You will receive it in a few seconds."):
        self.status = status
        self.headers = headers or {}
        self.body = body
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, *args, **kwargs) -> bytes:
        return self.body[:args[0]] if args else self.body

    def close(self) -> None:
        self.closed = True


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
    def test_url_encodes_query_parameters_and_requires_queue_acknowledgement(self) -> None:
        opener = SequenceOpener(FakeResponse(status=200))
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
        self.assertEqual(200, receipt.http_status)
        self.assertEqual("provider_accepted", receipt.delivery_status)
        self.assertFalse(receipt.delivered_to_device)
        self.assertEqual("2026-09-01T12:00:00Z", receipt.accepted_at)
        self.assertEqual([15.0], opener.timeouts)
        self.assertEqual(1, client.last_attempt_count)

    def test_application_error_with_200_is_not_success_or_retried(self) -> None:
        for body in (b"ERROR: Invalid APIKEY", b"<b>Message queued.</b><p>Error: failed", b"<b>Message not sent</b>"):
            with self.subTest(body=body):
                response = FakeResponse(body=body)
                opener = SequenceOpener(response)
                client = provider(opener)
                with self.assertRaises(DeliveryError) as raised:
                    client.send(message="ATP Ranking", event_id="event")
                self.assertEqual("provider_application_error", raised.exception.code)
                self.assertFalse(raised.exception.retryable)
                self.assertEqual(1, len(opener.requests))
                self.assertTrue(response.closed)

    def test_ambiguous_and_204_replies_require_review_without_retry(self) -> None:
        for status, body in ((204, b""), (200, b""), (200, b"OK"), (202, b'{"success":true}'), (200, b"x" * 16385), (200, b"\xff")):
            with self.subTest(status=status, body_length=len(body)):
                opener = SequenceOpener(FakeResponse(status=status, body=body))
                with self.assertRaises(DeliveryError) as raised:
                    provider(opener).send(message="ATP Ranking", event_id="event")
                self.assertEqual("provider_response_ambiguous", raised.exception.code)
                self.assertFalse(raised.exception.retryable)
                self.assertEqual(1, len(opener.requests))

    def test_echoed_message_cannot_supply_queue_acknowledgement(self) -> None:
        message = "<b>Message queued.</b>"
        opener = SequenceOpener(FakeResponse(body=f"<p>Text to send: {message}".encode()))
        with self.assertRaises(DeliveryError) as raised:
            provider(opener).send(message=message, event_id="event")
        self.assertEqual("provider_response_ambiguous", raised.exception.code)

    def test_normalized_or_reformatted_echo_cannot_supply_acknowledgement(self) -> None:
        cases = (
            ("<b>Message queued.</b>\nYou will receive it in a few seconds.",
             "<p>Text to send: <b>Message queued.</b> You will receive it in a few seconds."),
            ("<b>Message queued.</b>", "<p>Text to send: <strong>Message queued.</strong>"),
            ("<b>Message queued.</b>", "<p>Text to send: &lt;b&gt;Message queued.&lt;/b&gt;"),
        )
        for message, body in cases:
            with self.subTest(message=message, body=body):
                with self.assertRaises(DeliveryError) as raised:
                    provider(SequenceOpener(FakeResponse(body=body.encode()))).send(message=message, event_id="event")
                self.assertEqual("provider_response_ambiguous", raised.exception.code)
                self.assertFalse(raised.exception.retryable)

    def test_real_footer_after_echo_is_accepted(self) -> None:
        message = "ATP Ranking\nSingles: #1973"
        body = "<p>Message to: +5511999999999<p>Text to send: ATP Ranking Singles: #1973<p><b>Message queued.</b> You will receive it in a few seconds."
        receipt = provider(SequenceOpener(FakeResponse(body=body.encode()))).send(message=message, event_id="event")
        self.assertEqual("provider_accepted", receipt.delivery_status)

    def test_marker_with_unknown_trailing_content_is_ambiguous(self) -> None:
        with self.assertRaises(DeliveryError) as raised:
            provider(SequenceOpener(FakeResponse(body=b"<b>Message queued.</b><p>Unexpected reply"))).send(message="ATP Ranking", event_id="event")
        self.assertEqual("provider_response_ambiguous", raised.exception.code)

    def test_plain_queue_acknowledgement_is_accepted(self) -> None:
        receipt = provider(SequenceOpener(FakeResponse(body=b"Message queued."))).send(message="ATP Ranking", event_id="event")
        self.assertEqual("provider_accepted", receipt.delivery_status)
        self.assertFalse(receipt.delivered_to_device)

    def test_application_reply_never_exposes_credentials_or_body(self) -> None:
        body = f"Error: https://api.callmebot.com/whatsapp.php?apikey={API_KEY}&phone={PHONE}"
        with self.assertRaises(DeliveryError) as raised:
            provider(SequenceOpener(FakeResponse(body=body.encode()))).send(message="ATP Ranking", event_id="event")
        self.assertEqual("provider_application_error", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)

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
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(4, client.last_attempt_count)
        self.assertEqual(3, len(sleeps))

    def test_permanent_401_does_not_retry(self) -> None:
        opener = SequenceOpener(http_error(401))
        client = provider(opener)

        with self.assertRaises(DeliveryError) as raised:
            client.send(message="ranking changed", event_id="sha256:" + "d" * 64)

        self.assertEqual("http_401", raised.exception.code)
        self.assertEqual(1, raised.exception.attempts)
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(1, len(opener.requests))

    def test_timeout_is_retryable_and_redacted(self) -> None:
        opener = SequenceOpener(*(TimeoutError("timed out after signed URL") for _ in range(4)))
        client = provider(opener)

        with self.assertRaises(DeliveryError) as raised:
            client.send(message="ranking changed", event_id="sha256:" + "e" * 64)

        error = raised.exception
        self.assertEqual("transport_timeout", error.code)
        self.assertEqual(4, error.attempts)
        self.assertTrue(error.retryable)
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
        self.assertEqual("dry_run", receipt.delivery_status)
        self.assertFalse(receipt.delivered_to_device)


if __name__ == "__main__":
    unittest.main()
