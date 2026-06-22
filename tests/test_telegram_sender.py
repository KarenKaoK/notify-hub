import pytest
import requests

from telegram_sender import TelegramError, TelegramSender


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


def test_send_message_returns_message_id():
    session = FakeSession(FakeResponse(200, {"ok": True, "result": {"message_id": 7}}))
    sender = TelegramSender("token", session=session)
    assert sender.send_message("123", "hello") == 7
    assert session.calls[0][1]["json"] == {"chat_id": "123", "text": "hello"}


def test_send_message_wraps_network_errors():
    sender = TelegramSender("token", session=FakeSession(error=requests.Timeout()))
    with pytest.raises(TelegramError, match="request failed"):
        sender.send_message("123", "hello")


def test_send_message_rejects_telegram_error():
    response = FakeResponse(400, {"ok": False, "description": "Bad Request"})
    sender = TelegramSender("token", session=FakeSession(response))
    with pytest.raises(TelegramError, match="Bad Request"):
        sender.send_message("123", "hello")
