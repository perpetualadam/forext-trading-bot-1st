"""Guarantees the audit path cannot reach broker writes or live registries."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

# Modules the offline engine is forbidden to import.
FORBIDDEN_MODULES = (
    "forex_bot.oanda_exec",
    "forex_bot.oanda_client",
    "forex_bot.database",
    "forex_bot.orders",
    "forex_bot.positions",
    "forex_bot.bot_loop",
    "forex_bot.reconciliation",
)

FORBIDDEN_NAMES = (
    "execute_oanda_market_open",
    "execute_oanda_position_close",
    "OrderCreate",
    "PositionClose",
    "execute_trade",
    "open_position",
    "close_position",
    "log_trade_pg",
)


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def iter_package_sources() -> list[Path]:
    skip = {"__init__.py", "isolation.py"}
    return sorted(p for p in _package_dir().glob("*.py") if p.name not in skip)


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
                for alias in node.names:
                    imported.add(f"{node.module}.{alias.name}")
    for name in FORBIDDEN_MODULES:
        if name in imported or any(item.startswith(name + ".") for item in imported):
            hits.append(f"import:{name}")
    import re

    for name in FORBIDDEN_NAMES:
        if re.search(rf"\b{re.escape(name)}\b", source):
            hits.append(f"name:{name}")
    return hits


def assert_package_cannot_write_broker() -> list[str]:
    """Return empty list if every package file is isolated. Raises if any hit is found."""
    all_hits: list[str] = []
    for path in iter_package_sources():
        text = path.read_text(encoding="utf-8")
        hits = forbidden_hits_in_source(text)
        all_hits.extend(f"{path.name}:{h}" for h in hits)
    if all_hits:
        raise AssertionError("decision_quality broker-isolation violated: " + ", ".join(all_hits))
    return all_hits


def module_imports_forbidden(module: object) -> list[str]:
    src = inspect.getsource(module)
    return forbidden_hits_in_source(src)
