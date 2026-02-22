import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from apps.telegram_bot.telegram_bot import (
    ApiClientError,
    BotState,
    _api,
    _extract_server_error_message,
)


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: Any = ..., text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is ...:
            raise ValueError("not json")
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def request(self, *args, **kwargs):
        return self._response


def _state() -> BotState:
    return BotState(
        api_base="http://127.0.0.1:8765",
        api_key="k",
        admin_password="pwd",
        auth_file=Path("/tmp/telegram_auth.json"),
        authed_user_ids=set(),
        pending_run=set(),
        subscriptions={},
        draft_configs={},
    )


def test_extract_server_error_message_includes_hint_and_request_id() -> None:
    msg = _extract_server_error_message(
        {
            "ok": False,
            "error": {
                "code": "config_not_found",
                "message": "config not found",
                "hint": "Use /configs first",
                "request_id": "req-42",
            },
        }
    )
    assert msg == "config not found (hint: Use /configs first) [request_id=req-42]"


def test_api_raises_structured_error_message() -> None:
    response = _FakeResponse(
        status_code=404,
        payload={
            "ok": False,
            "error": {
                "code": "config_not_found",
                "message": "config not found",
                "hint": "Use /configs first",
                "request_id": "req-42",
            },
        },
    )
    client = _FakeClient(response)

    with pytest.raises(ApiClientError) as exc:
        asyncio.run(_api(cast(Any, client), _state(), "GET", "/configs/missing"))

    assert exc.value.status_code == 404
    assert "config not found" in str(exc.value)
    assert "request_id=req-42" in str(exc.value)


def test_api_rejects_success_response_without_json_body() -> None:
    response = _FakeResponse(status_code=200, payload=..., text="<html>bad</html>")
    client = _FakeClient(response)

    with pytest.raises(ApiClientError) as exc:
        asyncio.run(_api(cast(Any, client), _state(), "GET", "/runs"))

    assert exc.value.status_code == 200
    assert str(exc.value) == "Invalid JSON response from server"
