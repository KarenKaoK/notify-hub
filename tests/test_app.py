from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import create_app
from telegram_sender import TelegramError


VALID_PAYLOAD = {
    "type": "budget_summary",
    "total_expense": -736.42,
    "total_income": 0,
    "balance": -736.42,
    "categories": {
        "交": 126,
        "食": 372.14,
        "日": 167.51,
        "保險": 5.8,
        "運": 64.97,
    },
}


class FakeSender:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def send_message(self, chat_id, text):
        self.calls.append((chat_id, text))
        if self.error:
            raise self.error
        return 12345


@pytest.fixture
def sender():
    return FakeSender()


@pytest.fixture
def client(sender):
    berlin_time = datetime(2026, 6, 21, 18, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    app = create_app(
        sender=sender,
        api_secret="test-secret",
        chat_id="999",
        now_provider=lambda: berlin_time,
    )
    app.testing = True
    return app.test_client()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_notify_formats_and_sends_confirmed_message(client, sender):
    response = client.post(
        "/notify",
        json=VALID_PAYLOAD,
        headers={"X-Notify-Secret": "test-secret"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "message_id": 12345}
    assert sender.calls[0][0] == "999"
    text = sender.calls[0][1]
    assert "第 3 週累積額度：€300.00" in text
    assert "累積已花費（日+食）：€539.65" in text
    assert "週預算剩餘：-€239.65 ⚠️ 已超支" in text
    assert "更新時間：2026-06-21 18:30" in text


def test_rejects_wrong_secret(client, sender):
    response = client.post(
        "/notify", json=VALID_PAYLOAD, headers={"X-Notify-Secret": "wrong"}
    )
    assert response.status_code == 401
    assert sender.calls == []


def test_rejects_invalid_payload(client, sender):
    payload = dict(VALID_PAYLOAD)
    payload["categories"] = {"交": 1}
    response = client.post(
        "/notify",
        json=payload,
        headers={"X-Notify-Secret": "test-secret"},
    )
    assert response.status_code == 422
    assert sender.calls == []


def test_returns_bad_gateway_when_telegram_fails():
    app = create_app(
        sender=FakeSender(TelegramError("failed")),
        api_secret="test-secret",
        chat_id="999",
    )
    app.testing = True
    response = app.test_client().post(
        "/notify",
        json=VALID_PAYLOAD,
        headers={"X-Notify-Secret": "test-secret"},
    )
    assert response.status_code == 502
    assert response.get_json()["error"] == "Telegram delivery failed"
