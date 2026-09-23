"""Pull Telegram Cloud command/webhook state without touching trading."""

from __future__ import annotations

import json

from forex_bot.telegram_cloud import (
    cloud_parity_snapshot,
    mask_token,
    next_update_offset,
    parse_api_payload,
    parse_bot_identity,
    parse_commands,
    parse_inbound_text,
    parse_updates,
    parse_webhook,
    retry_after_seconds,
    telegram_method_url,
    webhook_conflicts_with_local_alerts,
)


def test_mask_token_never_keeps_raw_secret():
    raw = "https://api.telegram.org/bot123456:SECRET/getMe"
    assert "SECRET" not in mask_token(raw, "123456:SECRET")
    assert "123456:SECRET" not in mask_token(raw)
    assert mask_token(raw).endswith("/bot<redacted>/getMe")


def test_parse_commands_strips_slash_and_skips_empty():
    rows = parse_commands(
        [
            {"command": "/status", "description": "Bot health"},
            {"command": "positions", "description": "Open trades"},
            {"command": "", "description": "ignore"},
            "bad",
        ]
    )
    assert rows == [
        {"command": "status", "description": "Bot health"},
        {"command": "positions", "description": "Open trades"},
    ]


def test_webhook_conflict_flag_and_sanitized_url():
    hook = parse_webhook(
        {
            "url": "https://cloud.example/bot123456:SECRET/telegram",
            "pending_update_count": 4,
            "last_error_message": "Connection timed out",
        },
        "123456:SECRET",
    )
    assert "SECRET" not in hook["url"]
    assert hook["pending_update_count"] == 4
    assert webhook_conflicts_with_local_alerts(hook) is True
    assert webhook_conflicts_with_local_alerts(parse_webhook({"url": ""})) is False


def test_cloud_parity_snapshot_says_local_does_not_handle_commands():
    snap = cloud_parity_snapshot(
        identity=parse_bot_identity({"id": 1, "username": "fx_bot"}),
        commands=[{"command": "status", "description": "Bot health"}],
        webhook=parse_webhook({"url": ""}),
    )
    assert snap["local_handles_inbound_commands"] is False
    assert snap["webhook_conflicts_with_local_alerts"] is False
    assert snap["identity"]["username"] == "fx_bot"
    assert snap["commands"][0]["command"] == "status"


def test_parse_api_payload_rejects_error_without_raising():
    assert parse_api_payload({"ok": False, "description": "Unauthorized", "error_code": 401}) == {
        "ok": False,
        "error": "Unauthorized",
        "error_code": 401,
    }
    assert parse_api_payload("nope")["ok"] is False


def test_parse_inbound_commands_and_plain_text():
    assert parse_inbound_text("/status@Quantumskiesbot") == {
        "text": "/status@Quantumskiesbot",
        "is_command": True,
        "command": "status",
    }
    assert parse_inbound_text("/positions EUR_USD")["command"] == "positions"
    assert parse_inbound_text("hello")["is_command"] is False


def test_parse_updates_and_ack_offset():
    rows = parse_updates(
        [
            {
                "update_id": 10,
                "message": {
                    "text": "/status",
                    "date": 1,
                    "chat": {"id": 99, "type": "private", "first_name": "skip-me"},
                },
            },
            {
                "update_id": 11,
                "message": {"text": "hi", "chat": {"id": 99, "type": "private"}},
            },
        ]
    )
    assert [r["command"] for r in rows] == ["status", ""]
    assert rows[0]["chat_id"] == 99
    assert "skip-me" not in json.dumps(rows)
    assert next_update_offset(rows) == 12


def test_fetch_pending_updates_parses_and_can_ack(monkeypatch):
    from forex_bot import telegram_cloud as tc

    calls = []

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=8.0):
        calls.append({"url": url, "params": params or {}})
        if params and params.get("offset") == 12:
            return _Resp({"ok": True, "result": []})
        return _Resp(
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 11,
                        "message": {"text": "/help", "chat": {"id": 1, "type": "private"}},
                    }
                ],
            }
        )

    monkeypatch.setattr(tc.requests, "get", fake_get)
    pulled = tc.fetch_pending_updates("tok", acknowledge=True)
    assert pulled["ok"] is True
    assert pulled["commands"] == ["help"]
    assert pulled["acknowledged"] is True
    assert calls[-1]["params"]["offset"] == 12


def test_set_local_command_menu_posts_readonly_list(monkeypatch):
    from forex_bot import telegram_cloud as tc
    from forex_bot.telegram_commands import local_command_menu

    posted = {}

    class _Resp:
        def json(self):
            return {"ok": True, "result": True}

    def fake_post(url, json=None, timeout=8.0):
        posted["url"] = url
        posted["json"] = json
        return _Resp()

    monkeypatch.setattr(tc.requests, "post", fake_post)
    result = tc.set_local_command_menu("tok", local_command_menu())
    assert result["ok"] is True
    assert posted["json"]["commands"] == local_command_menu()
    assert all(row["command"] in ("help", "status") for row in posted["json"]["commands"])


def test_retry_after_seconds_reads_telegram_429_body():
    assert retry_after_seconds(
        {"ok": False, "error_code": 429, "parameters": {"retry_after": 12}}
    ) == 12.0
    assert retry_after_seconds({"ok": False, "description": "Bad Gateway"}) is None
    assert retry_after_seconds("nope", default=5.0) == 5.0
    assert retry_after_seconds({}, header="7") == 7.0


def test_method_url_requires_token():
    url = telegram_method_url("abc", "getMe")
    assert url.endswith("/botabc/getMe")
    try:
        telegram_method_url("", "getMe")
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("expected ValueError")
