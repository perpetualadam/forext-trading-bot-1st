"""Prove Stage G research never imports broker-mutating production paths."""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
FORBIDDEN = {
    "forex_bot.oanda_exec",
    "forex_bot.bot_loop",
    "forex_bot.execution",
    "forex_bot.live_safety",
    "forex_bot.live_safety_preflight",
    "forex_bot.telegram_control",
    "forex_bot.app",
    "forex_bot.oanda_client",
    "forex_bot.oanda_candles_read",
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def forbidden_hits() -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for path in PACKAGE.glob("*.py"):
        mods = imported_modules(path)
        bad = sorted(m for m in mods if m in FORBIDDEN or any(m.startswith(f + ".") for f in FORBIDDEN))
        if bad:
            hits[path.name] = bad
    return hits
