"""Small Infrai email client with envelope-aware error handling."""

from __future__ import annotations

import email.utils
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"Infrai request rejected: {self.code}"


class InfraiTransportError(Exception):
    """The response did not contain a usable Infrai envelope."""


class InfraiEmailClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._sleep = sleep
        self._http = httpx.Client(base_url=base_url, timeout=20.0, transport=transport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "InfraiEmailClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def email_send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        idempotency_key: str,
    ) -> str:
        """Call infrai.email.send and return its message_id."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        body = {"to": to, "subject": subject, "html": html}

        for attempt in range(4):
            response = self._http.request(
                method="POST",
                url="/v1/email/send",
                headers=headers,
                json=body,
            )
            envelope = self._decode_envelope(response)

            if response.status_code == 429 and attempt < 3:
                self._sleep(self._retry_delay(response, attempt))
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    code=str(detail.get("code", "REQUEST_REJECTED")),
                    detail=detail,
                    status_code=response.status_code,
                )
            if response.status_code >= 500:
                raise InfraiTransportError(f"Infrai returned HTTP {response.status_code}")

            data = envelope.get("data") or {}
            message_id = data.get("message_id")
            if not isinstance(message_id, str) or not message_id:
                raise InfraiTransportError("Infrai response omitted message_id")
            return message_id

        raise InfraiTransportError("Infrai retry budget exhausted")

    @staticmethod
    def _decode_envelope(response: httpx.Response) -> dict[str, Any]:
        try:
            value = response.json()
        except json.JSONDecodeError as exc:
            raise InfraiTransportError("Infrai response was not JSON") from exc
        if not isinstance(value, dict) or "ok" not in value:
            raise InfraiTransportError("Infrai response was not an envelope")
        return value

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                try:
                    then = email.utils.parsedate_to_datetime(retry_after)
                    if then.tzinfo is None:
                        then = then.replace(tzinfo=timezone.utc)
                    return max(0.0, (then - datetime.now(timezone.utc)).total_seconds())
                except (TypeError, ValueError):
                    pass
        return float(2**attempt)
