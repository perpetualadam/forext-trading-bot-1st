"""Fetch Telegram Cloud command/webhook state. Never print the token."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from forex_bot.config import Config
from forex_bot.telegram_cloud import fetch_cloud_state, fetch_pending_updates
from forex_bot.telegram_commands import local_command_menu, sync_command_menu

OUT = Path("reports/telegram_cloud_parity.json")


def main() -> None:
    token = (Config.TELEGRAM_TOKEN or "").strip()
    state = fetch_cloud_state(token)
    state["retrieved_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state["chat_id_configured"] = bool((Config.TELEGRAM_CHAT_ID or "").strip())
    state["token_configured"] = bool(token)
    OUT.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("ok", state.get("ok"), "error", state.get("error"))
    print("commands", [c.get("command") for c in state.get("commands") or []])
    print("webhook_url", (state.get("webhook") or {}).get("url"))
    print("webhook_conflict", state.get("webhook_conflicts_with_local_alerts"))
    print("pending_updates", (state.get("webhook") or {}).get("pending_update_count"))
    print("last_error", (state.get("webhook") or {}).get("last_error_message"))
    pending = fetch_pending_updates(token, acknowledge=True)
    pending["retrieved_at_utc"] = state["retrieved_at_utc"]
    Path("reports/telegram_pending_updates.json").write_text(
        json.dumps(pending, indent=2), encoding="utf-8"
    )
    print("pending_ok", pending.get("ok"), "n", pending.get("n_updates"))
    print("pending_commands", pending.get("commands"))
    print("acknowledged", pending.get("acknowledged"))
    synced = sync_command_menu()
    print("menu_sync_ok", synced.get("ok"), synced.get("error") or synced.get("reason"))
    print("local_menu", [c["command"] for c in local_command_menu()])


if __name__ == "__main__":
    main()
