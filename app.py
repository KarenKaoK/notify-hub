"""Flask entry point for notify-hub."""

from __future__ import annotations

import hmac
import logging
import os
from datetime import datetime
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request

from budget_calculator import (
    ValidationError,
    calculate_budget,
    format_budget_message,
    money,
)
from telegram_sender import TelegramError, TelegramSender


BERLIN = ZoneInfo("Europe/Berlin")


class Sender(Protocol):
    def send_message(self, chat_id: str, text: str) -> int: ...


def create_app(
    *,
    sender: Sender | None = None,
    api_secret: str | None = None,
    chat_id: str | None = None,
    now_provider: Callable[[], datetime] | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["API_SECRET"] = api_secret or os.getenv("NOTIFY_API_SECRET", "")
    app.config["TELEGRAM_CHAT_ID"] = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
    app.config["SENDER"] = sender
    app.config["NOW_PROVIDER"] = now_provider or (lambda: datetime.now(BERLIN))

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/notify")
    def notify():
        secret = app.config["API_SECRET"]
        if not secret:
            app.logger.error("NOTIFY_API_SECRET is not configured")
            return _error("service is not configured", 503)

        supplied_secret = request.headers.get("X-Notify-Secret", "")
        if not hmac.compare_digest(supplied_secret, secret):
            return _error("unauthorized", 401)

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return _error("request body must be a JSON object", 400)
        if body.get("type") != "budget_summary":
            return _error("unsupported notification type", 422)

        try:
            total_expense = money(body.get("total_expense"), "total_expense")
            total_income = money(body.get("total_income"), "total_income")
            balance = money(body.get("balance"), "balance")
            now = app.config["NOW_PROVIDER"]()
            result = calculate_budget(body.get("categories"), now)
        except ValidationError as exc:
            return _error(str(exc), 422)

        text = format_budget_message(
            total_expense=total_expense,
            total_income=total_income,
            balance=balance,
            result=result,
            now=now,
        )

        configured_sender = app.config["SENDER"]
        configured_chat_id = app.config["TELEGRAM_CHAT_ID"]
        if configured_sender is None:
            token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            if token:
                configured_sender = TelegramSender(token)
        if configured_sender is None or not configured_chat_id:
            app.logger.error("Telegram sender or chat ID is not configured")
            return _error("service is not configured", 503)

        try:
            message_id = configured_sender.send_message(configured_chat_id, text)
        except TelegramError:
            # Do not log the chained requests exception: its URL contains the bot token.
            app.logger.error("Telegram delivery failed")
            return _error("Telegram delivery failed", 502)

        return jsonify(status="ok", message_id=message_id)

    return app


def _error(message: str, status_code: int):
    return jsonify(status="error", error=message), status_code


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")))
