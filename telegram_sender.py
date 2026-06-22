"""Small Telegram Bot API client."""

from __future__ import annotations

from typing import Any

import requests


class TelegramError(RuntimeError):
    """Raised when Telegram rejects or cannot complete a send request."""


class TelegramSender:
    def __init__(
        self,
        bot_token: str,
        *,
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        if not bot_token:
            raise ValueError("Telegram bot token is required")
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.timeout = timeout
        self.session = session or requests.Session()

    def send_message(self, chat_id: str, text: str) -> int:
        try:
            response = self.session.post(
                self.url,
                json={"chat_id": chat_id, "text": text},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TelegramError("Telegram request failed") from exc

        try:
            body: dict[str, Any] = response.json()
        except ValueError as exc:
            raise TelegramError(
                f"Telegram returned HTTP {response.status_code} with invalid JSON"
            ) from exc

        if response.status_code >= 400 or not body.get("ok"):
            description = str(body.get("description", "Telegram rejected the message"))
            raise TelegramError(
                f"Telegram returned HTTP {response.status_code}: {description}"
            )

        try:
            return int(body["result"]["message_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TelegramError("Telegram response did not contain message_id") from exc
