"""Notification providers with bounded retries and secret-safe failures."""

from __future__ import annotations

import os
import random
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Protocol

CALLMEBOT_ENDPOINT = "https://api.callmebot.com/whatsapp.php"
_E164_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")


class ConfigurationError(ValueError):
    def __init__(self, code: str = "invalid_configuration"):
        self.code = code
        super().__init__(code)


class DeliveryError(RuntimeError):
    def __init__(self, code: str, attempts: int):
        self.code = code
        self.attempts = attempts
        super().__init__(code)


@dataclass(frozen=True, kw_only=True)
class DeliveryReceipt:
    provider: str
    accepted_at: str
    http_status: int | None


class NotificationProvider(Protocol):
    name: str

    def send(self, *, message: str, event_id: str) -> DeliveryReceipt: ...


def validate_callmebot_config(phone: str | None, api_key: str | None) -> tuple[str, str]:
    normalized_phone = (phone or "").strip()
    normalized_key = (api_key or "").strip()
    if not _E164_RE.fullmatch(normalized_phone) or not normalized_key:
        raise ConfigurationError()
    return normalized_phone, normalized_key


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _retry_after_seconds(value: str | None, now: datetime) -> float | None:
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(int(value))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            seconds = (parsed.astimezone(timezone.utc) - now.astimezone(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0.0, min(120.0, seconds))


class CallMeBotProvider:
    name = "callmebot"

    def __init__(
        self,
        *,
        phone: str,
        api_key: str,
        opener: Callable[..., object] = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
        random_uniform: Callable[[float, float], float] = random.uniform,
        now: Callable[[], datetime] = _utc_now,
        timeout: float = 15.0,
        max_attempts: int = 4,
    ) -> None:
        self._phone, self._api_key = validate_callmebot_config(phone, api_key)
        if timeout <= 0 or max_attempts < 1:
            raise ConfigurationError()
        self._opener = opener
        self._sleep = sleep
        self._random_uniform = random_uniform
        self._now = now
        self._timeout = timeout
        self._max_attempts = max_attempts
        self.last_attempt_count = 0

    @classmethod
    def from_env(cls, **kwargs: object) -> "CallMeBotProvider":
        return cls(
            phone=os.environ.get("CALLMEBOT_PHONE", ""),
            api_key=os.environ.get("CALLMEBOT_API_KEY", ""),
            **kwargs,
        )

    def _delay(self, *, retry_after: str | None, attempt: int) -> float:
        specified = _retry_after_seconds(retry_after, self._now())
        if specified is not None:
            return specified
        ceiling = min(30.0, 2.0 ** (attempt - 1))
        return max(0.0, self._random_uniform(0.0, ceiling))

    def send(self, *, message: str, event_id: str) -> DeliveryReceipt:
        if not isinstance(message, str) or not message.strip() or not isinstance(event_id, str) or not event_id:
            raise DeliveryError("invalid_message", 0)
        self.last_attempt_count = 0

        # The credential-bearing URL exists only in this method and is never
        # included in returned values or propagated exception messages.
        query = urllib.parse.urlencode(
            {"phone": self._phone, "text": message, "apikey": self._api_key}
        )
        request = urllib.request.Request(f"{CALLMEBOT_ENDPOINT}?{query}", method="GET")

        for attempt in range(1, self._max_attempts + 1):
            self.last_attempt_count = attempt
            retry_after: str | None = None
            try:
                response = self._opener(request, timeout=self._timeout)
                raw_status = getattr(response, "status", None)
                if raw_status is None:
                    raw_status = response.getcode()
                status = int(raw_status)
                close = getattr(response, "close", None)
                if callable(close):
                    close()
                if 200 <= status < 300:
                    return DeliveryReceipt(
                        provider=self.name,
                        accepted_at=_timestamp(self._now()),
                        http_status=status,
                    )
                retryable = status in {408, 429} or 500 <= status <= 599
                code = f"http_{status}"
            except urllib.error.HTTPError as exc:
                status = int(exc.code)
                retry_after = exc.headers.get("Retry-After") if exc.headers is not None else None
                retryable = status in {408, 429} or 500 <= status <= 599
                code = f"http_{status}"
            except (TimeoutError, socket.timeout):
                retryable = True
                code = "transport_timeout"
            except (urllib.error.URLError, ConnectionError, OSError):
                retryable = True
                code = "transport_error"
            except Exception:
                # Unknown adapter failures are deliberately redacted and not
                # retried, because their delivery semantics are not known.
                raise DeliveryError("provider_error", attempt) from None

            if not retryable or attempt == self._max_attempts:
                raise DeliveryError(code, attempt) from None
            self._sleep(self._delay(retry_after=retry_after, attempt=attempt))

        raise DeliveryError("provider_error", self.last_attempt_count)


class DryRunProvider:
    name = "dry-run"

    def __init__(self, now: Callable[[], datetime] = _utc_now) -> None:
        self._now = now
        self.messages: list[tuple[str, str]] = []
        self.last_attempt_count = 0

    def send(self, *, message: str, event_id: str) -> DeliveryReceipt:
        self.messages.append((event_id, message))
        return DeliveryReceipt(provider=self.name, accepted_at=_timestamp(self._now()), http_status=None)
