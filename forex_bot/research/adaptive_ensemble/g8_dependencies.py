"""Classify the 86 modules Stage G.7 left as UNKNOWN. Does not delete anything."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = ROOT / "data" / "research" / "adaptive_ensemble" / "g7" / "snapshot_context.json"


def _module_name(rel: str) -> str:
    if rel.endswith(".py"):
        name = rel[:-3].replace("/", ".")
        if name.endswith(".__init__"):
            return name[: -len(".__init__")]
        return name
    return ""


def _imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _module_file(module: str) -> Path | None:
    if not module.startswith("forex_bot"):
        return None
    parts = module.split(".")
    direct = ROOT.joinpath(*parts).with_suffix(".py")
    if direct.is_file():
        return direct
    init = ROOT.joinpath(*parts, "__init__.py")
    if init.is_file():
        return init
    return None


def production_reachable() -> set[str]:
    """Static imports from the production process, including imports inside functions."""
    queue = ["forex_bot.app", "forex_bot.bot_loop", "main"]
    seen: set[str] = set()
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        path = _module_file(module)
        if path is None:
            continue
        for imported in _imports(path):
            if imported != "forex_bot" and not imported.startswith("forex_bot."):
                continue
            parts = imported.split(".")
            for index in range(1, len(parts) + 1):
                queue.append(".".join(parts[:index]))
    return seen


def _importers() -> dict[str, list[str]]:
    incoming: dict[str, list[str]] = {}
    for path in (ROOT / "forex_bot").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for imported in _imports(path):
            incoming.setdefault(imported, []).append(rel)
    for path in (ROOT / "tests").glob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        for imported in _imports(path):
            incoming.setdefault(imported, []).append(rel)
    return incoming


def _classify_one(rel: str, reachable: set[str], incoming: dict[str, list[str]]) -> dict[str, str]:
    module = _module_name(rel)
    callers = sorted(set(incoming.get(module, [])))
    production_callers = [
        item
        for item in callers
        if item.startswith("forex_bot/")
        and "research/" not in item
        and "decision_quality/" not in item
        and "/shadow/" not in item
        and not item.endswith(("/backtest.py", "/csv_ohlcv.py", "/oanda_candles_read.py"))
    ]
    if module and module in reachable:
        return {
            "path": rel,
            "classification": "PRODUCTION_REQUIRED",
            "evidence": "static import reachable from forex_bot.app or forex_bot.bot_loop",
        }
    if production_callers:
        return {
            "path": rel,
            "classification": "UNRESOLVED",
            "evidence": "imported outside the startup closure by " + ",".join(production_callers),
        }
    if rel == "forex_bot/decision_repair/harness.py":
        return {
            "path": rel,
            "classification": "TEST_ONLY",
            "evidence": "imported by decision-repair tests; not imported by app, bot_loop, execution, or oanda_exec",
        }
    if rel == "forex_bot/live_safety_preflight.py":
        return {
            "path": rel,
            "classification": "OPTIONAL_OPERATIONAL_TOOL",
            "evidence": "operator writer for the durable blocked file; process start uses live_safety.initialise_fail_closed and denies when that file is absent",
        }
    if rel in {"forex_bot/backtest.py", "forex_bot/csv_ohlcv.py", "forex_bot/oanda_candles_read.py"}:
        return {
            "path": rel,
            "classification": "RESEARCH_ONLY",
            "evidence": "offline history or CSV path; no production startup import and no order-create call",
        }
    if rel.startswith("forex_bot/v2_shadow/"):
        return {
            "path": rel,
            "classification": "RESEARCH_ONLY",
            "evidence": "not imported by forex_bot.v2_shadow package initialisation or by bot_loop",
        }
    if rel.startswith(("forex_bot/decision_quality/", "forex_bot/shadow/")):
        return {
            "path": rel,
            "classification": "RESEARCH_ONLY",
            "evidence": "offline package; no import edge from the production startup closure",
        }
    return {
        "path": rel,
        "classification": "UNRESOLVED",
        "evidence": "no demonstrated importer; exclusion is not approved",
    }


def classify_unknowns() -> dict[str, Any]:
    context = json.loads(CONTEXT.read_text(encoding="utf-8"))
    unknown = list(context["unknown_modules"])
    reachable = production_reachable()
    incoming = _importers()
    rows = [_classify_one(rel, reachable, incoming) for rel in unknown]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    dynamic: list[str] = []
    for path in (ROOT / "forex_bot").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            dynamic.append(path.relative_to(ROOT).as_posix() + ":unparsed")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            dynamic_call = isinstance(func, ast.Name) and func.id == "__import__"
            dynamic_call = dynamic_call or (isinstance(func, ast.Attribute) and func.attr == "import_module")
            if dynamic_call:
                dynamic.append(path.relative_to(ROOT).as_posix())
                break
    return {
        "previously_unknown": len(unknown),
        "counts": counts,
        "unresolved": [row["path"] for row in rows if row["classification"] == "UNRESOLVED"],
        "dynamic_import_sites": dynamic,
        "minimal_production_set_approved": False,
        "approval_reason": "classifications are evidence for a later image; the Dockerfile still copies the whole package and no reduced image was assembled",
        "rows": rows,
    }
