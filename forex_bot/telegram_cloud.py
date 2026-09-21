"""Read Telegram Bot API cloud state without changing trading.

BotFather / setMyCommands / setWebhook live on Telegram's servers. This module
pulls that menu and webhook info so local code can stay in parity. It does not
poll getUpdates, place trades, or register new commands.
"""

from __future__ import annotations

import re
from typing import Any

import requests

TELEGRAM_API_ROOT = "https://api.telegram.org"


def mask_token(url: str, token: str = "") -> str:
    """Never persist or log a raw bot token."""
    text = str(url or "")
    if token:
        text = text.replace(token, "<redacted>")
    return re.sub(r"/bot[^/\s]+", "/bot<redacted>", text)


def telegram_method_url(token: str, method: str) -> str:
    t = (token or "").strip()
    if not t:
        raise ValueError("telegram token missing")
    return f"{TELEGRAM_API_ROOT}/bot{t}/{method}"


def parse_api_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "error": "non_object_response"}
    if payload.get("ok") is not True:
        desc = payload.get("description") or payload.get("error") or "telegram_api_not_ok"
        return {"ok": False, "error": str(desc), "error_code": payload.get("error_code")}
    return {"ok": True, "result": payload.get("result")}


def parse_bot_identity(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    return {
        "id": result.get("id"),
        "username": result.get("username"),
        "can_join_groups": result.get("can_join_groups"),
        "can_read_all_group_messages": result.get("can_read_all_group_messages"),
        "supports_inline_queries": result.get("supports_inline_queries"),
    }


def parse_commands(result: Any) -> list[dict[str, str]]:
    if not isinstance(result, list):
        return []
    out: list[dict[str, str]] = []
    for row in result:
        if not isinstance(row, dict):
            continue
        name = str(row.get("command") or "").strip().lstrip("/")
        if not name:
            continue
        out.append({"command": name, "description": str(row.get("description") or "")})
    return out


def parse_webhook(result: Any, token: str = "") -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"url": "", "has_custom_certificate": False, "pending_update_count": 0}
    url = mask_token(str(result.get("url") or ""), token)
    return {
        "url": url,
        "has_custom_certificate": bool(result.get("has_custom_certificate")),
        "pending_update_count": int(result.get("pending_update_count") or 0),
        "last_error_date": result.get("last_error_date"),
        "last_error_message": result.get("last_error_message"),
        "ip_address": result.get("ip_address"),
        "allowed_updates": list(result.get("allowed_updates") or []),
    }


_COMMAND_RE = re.compile(r"^/([a-zA-Z0-9_]+)(?:@\w+)?(?:\s+|$)")


def parse_inbound_text(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    match = _COMMAND_RE.match(raw)
    if not match:
        return {"text": raw[:200], "is_command": False, "command": ""}
    return {"text": raw[:200], "is_command": True, "command": match.group(1).lower()}


def parse_updates(result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, list):
        return []
    out: list[dict[str, Any]] = []
    for row in result:
        if not isinstance(row, dict):
            continue
        msg = row.get("message") or row.get("edited_message") or {}
        if not isinstance(msg, dict):
            msg = {}
        chat = msg.get("chat") if isinstance(msg.get("chat"), dict) else {}
        parsed = parse_inbound_text(str(msg.get("text") or ""))
        out.append(
            {
                "update_id": row.get("update_id"),
                "chat_id": chat.get("id"),
                "chat_type": chat.get("type"),
                "date": msg.get("date"),
                **parsed,
            }
        )
    return out


def next_update_offset(updates: list[dict[str, Any]]) -> int | None:
    ids = [u.get("update_id") for u in updates if isinstance(u.get("update_id"), int)]
    if not ids:
        return None
    return max(ids) + 1


def webhook_conflicts_with_local_alerts(webhook: dict[str, Any]) -> bool:
    """A leftover cloud webhook can swallow inbound commands and surface 409s."""
    return bool((webhook.get("url") or "").strip())


def cloud_parity_snapshot(
    *,
    identity: dict[str, Any],
    commands: list[dict[str, str]],
    webhook: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source": "telegram_bot_api",
        "identity": identity,
        "commands": commands,
        "webhook": webhook,
        "local_handles_inbound_commands": False,
        "webhook_conflicts_with_local_alerts": webhook_conflicts_with_local_alerts(webhook),
        "parity_note": (
            "Local app only sends sendMessage alerts. Slash commands registered in "
            "Telegram Cloud do nothing until inbound getUpdates/webhook handling exists."
        ),
    }


def fetch_cloud_state(token: str, timeout: float = 8.0) -> dict[str, Any]:
    """GET getMe, getMyCommands, getWebhookInfo. Never includes the token in the result."""
    t = (token or "").strip()
    if not t:
        return {"ok": False, "error": "telegram_token_missing"}

    def _get(method: str) -> dict[str, Any]:
        resp = requests.get(telegram_method_url(t, method), timeout=timeout)
        try:
            body = resp.json()
        except ValueError:
            return {"ok": False, "error": f"non_json_{resp.status_code}"}
        parsed = parse_api_payload(body)
        if not parsed.get("ok"):
            return parsed
        return parsed

    me = _get("getMe")
    if not me.get("ok"):
        return {"ok": False, "error": me.get("error"), "step": "getMe"}
    cmds = _get("getMyCommands")
    if not cmds.get("ok"):
        return {"ok": False, "error": cmds.get("error"), "step": "getMyCommands"}
    hook = _get("getWebhookInfo")
    if not hook.get("ok"):
        return {"ok": False, "error": hook.get("error"), "step": "getWebhookInfo"}
    snapshot = cloud_parity_snapshot(
        identity=parse_bot_identity(me.get("result")),
        commands=parse_commands(cmds.get("result")),
        webhook=parse_webhook(hook.get("result"), t),
    )
    snapshot["ok"] = True
    return snapshot


def fetch_pending_updates(token: str, timeout: float = 8.0, *, acknowledge: bool = False) -> dict[str, Any]:
    """One-shot getUpdates. Does not execute commands or change trading."""
    t = (token or "").strip()
    if not t:
        return {"ok": False, "error": "telegram_token_missing"}
    resp = requests.get(telegram_method_url(t, "getUpdates"), params={"timeout": 0}, timeout=timeout)
    try:
        body = resp.json()
    except ValueError:
        return {"ok": False, "error": f"non_json_{resp.status_code}"}
    parsed = parse_api_payload(body)
    if not parsed.get("ok"):
        return parsed
    updates = parse_updates(parsed.get("result"))
    offset = next_update_offset(updates)
    acknowledged = False
    if acknowledge and offset is not None:
        ack = requests.get(
            telegram_method_url(t, "getUpdates"),
            params={"timeout": 0, "offset": offset},
            timeout=timeout,
        )
        try:
            ack_body = ack.json()
        except ValueError:
            ack_body = {}
        acknowledged = bool(parse_api_payload(ack_body).get("ok"))
    return {
        "ok": True,
        "updates": updates,
        "n_updates": len(updates),
        "commands": [u["command"] for u in updates if u.get("is_command")],
        "next_offset": offset,
        "acknowledged": acknowledged,
    }


def set_local_command_menu(token: str, commands: list[dict[str, str]], timeout: float = 8.0) -> dict[str, Any]:
    """Replace Telegram Cloud command menu with the local read-only list."""
    t = (token or "").strip()
    if not t:
        return {"ok": False, "error": "telegram_token_missing"}
    resp = requests.post(
        telegram_method_url(t, "setMyCommands"),
        json={"commands": commands},
        timeout=timeout,
    )
    try:
        body = resp.json()
    except ValueError:
        return {"ok": False, "error": f"non_json_{resp.status_code}"}
    return parse_api_payload(body)
