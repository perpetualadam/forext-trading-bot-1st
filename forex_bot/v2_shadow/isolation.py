"""Static fail-closed: this package must never import or name execution writes."""

from __future__ import annotations

import ast
import re
from pathlib import Path

FORBIDDEN_MODULES = (
    "forex_bot.oanda_exec",
    "forex_bot.oanda_client",
    "forex_bot.database",
    "forex_bot.orders",
    "forex_bot.bot_loop",
    "forex_bot.reconciliation",
    "forex_bot.positions",
)

FORBIDDEN_NAMES = (
    "execute_oanda_market_open",
    "execute_oanda_position_close",
    "PositionClose",
    "execute_trade",
    "open_position",
    "close_position",
    "log_trade_pg",
    "try_begin_order_submission",
    "V2_LIVE_ENABLED",
)


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def forbidden_hits_in_source(source: str) -> list[str]:
    hits: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ["syntax_error"]
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
    for name in FORBIDDEN_MODULES:
        if name in imported or any(item.startswith(name + ".") for item in imported):
            hits.append(f"import:{name}")
    for name in FORBIDDEN_NAMES:
        if re.search(rf"\b{re.escape(name)}\b", source):
            hits.append(f"name:{name}")
    return hits


def assert_v2_cannot_write_broker() -> list[str]:
    all_hits: list[str] = []
    for path in sorted(_package_dir().glob("*.py")):
        if path.name == "isolation.py":
            continue
        hits = forbidden_hits_in_source(path.read_text(encoding="utf-8"))
        all_hits.extend(f"{path.name}:{h}" for h in hits)
    if all_hits:
        raise AssertionError("v2_shadow execution isolation violated: " + ", ".join(all_hits))
    return all_hits
