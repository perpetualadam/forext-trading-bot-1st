"""Reuse selected existing definitions without executing production module bodies.

No config, model-store, broker or journal imports. AST identity is pinned so LF
and CRLF checkouts use the same reviewed functions; raw source hashes are also
reported, never substituted for the operational source seal.
"""
from __future__ import annotations

import __future__
import ast
import builtins
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import logging
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Protocol

from .core import ResearchRejected, pip_size

SPECS = {
    "forex_bot/shadow/reasons.py": ["ShadowReason"],
    "forex_bot/shadow/signals.py": ["signal_from_arrays"],
    "forex_bot/shadow/original.py": ["hybrid_family", "select_name_argmax"],
    "forex_bot/ai_ensemble.py": ["AIEnsemble", "ExternalLLMAPI", "LocalLLM", "_quant_stub_vote"],
    "forex_bot/rl_agent.py": ["RLAgent"],
    "forex_bot/profit_protection.py": ["apply_profit_protection"],
    "forex_bot/indicators.py": ["compute_indicators", "latest_atr_price"],
    "forex_bot/trading.py": ["sl_tp_distance_for_entry"],
}


def selected_nodes(path, entry):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    definitions = {n.name: n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
    selected, pending = set(), list(entry)
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        if name not in definitions:
            raise ResearchRejected("missing_reused_definition:" + name)
        selected.add(name)
        pending.extend(n.id for n in ast.walk(definitions[name])
                       if isinstance(n, ast.Name) and n.id in definitions and n.id not in selected)
    return [n for n in tree.body if getattr(n, "name", None) in selected]


def canonical_ast(node):
    """Version-neutral AST encoding: Python 3.13 dump omits 3.12 empty fields."""
    def encode(value):
        if isinstance(value, ast.AST):
            return [type(value).__name__, {key: encode(item) for key, item in ast.iter_fields(value)
                                          if item is not None and item != []}]
        if isinstance(value, list):
            return [encode(item) for item in value]
        if value is Ellipsis or isinstance(value, (bytes, complex)):
            return {'literal_type':type(value).__name__,'repr':repr(value)}
        return value
    return json.dumps(encode(node),sort_keys=True,separators=(',',':'))


def source_manifest(root):
    result = {}
    for relative, entry in SPECS.items():
        path = root / relative
        nodes = selected_nodes(path, entry)
        canonical = canonical_ast(ast.Module(body=nodes, type_ignores=[]))
        result[relative] = {"entry": entry, "definitions": [n.name for n in nodes],
                            "ast_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
                            "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if relative.endswith('/trading.py'):
            tree=ast.parse(path.read_text(encoding='utf-8-sig'))
            result[relative]['constants']={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body
                if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
                and n.targets[0].id in ('SL_FALLBACK_PIPS','TP_RISK_REWARD')}
    return result


def _import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "forex_bot.symbols":
        return SimpleNamespace(quote_currency=lambda symbol: symbol.split("_")[1])
    if name == "forex_bot.indicators":
        # Actual PP is given the causal ATR14 value. Missing ATR stays missing;
        # this shim never imports pandas or invents a computed value.
        return SimpleNamespace(latest_atr_price=lambda frame, period: None)
    if name == 'forex_bot.profit_protection':
        return SimpleNamespace(pip_size=pip_size)
    raise ResearchRejected("reused_function_import_refused:" + name)


class Existing:
    def __init__(self, root):
        manifest = json.loads((Path(__file__).parent / "reuse_manifest.json").read_text(encoding="utf-8"))
        actual = source_manifest(root)
        for path, record in actual.items():
            if record["ast_sha256"] != manifest[path]["ast_sha256"]:
                raise ResearchRejected("reused_source_changed:" + path)
            if record.get('constants') != manifest[path].get('constants'):
                raise ResearchRejected('reused_source_constants_changed:'+path)
        self.sources = actual
        reasons = None
        for relative, entry in SPECS.items():
            name = "tiv2_reused_" + Path(relative).stem
            module = ModuleType(name)
            sys.modules[name] = module
            logger = logging.getLogger(name)
            logger.handlers = [logging.NullHandler()]
            logger.propagate = False
            namespace = module.__dict__
            namespace.update(Any=Any, Protocol=Protocol, math=math, dataclass=dataclass, StrEnum=StrEnum,
                             logger=logger, os=SimpleNamespace(getenv=lambda key: None),
                             _ACTIONS=("BUY", "SELL", "SKIP"), ShadowReason=reasons,
                             __builtins__={**vars(builtins), "__import__": _import})
            namespace.update(actual[relative].get('constants',{}))
            nodes = selected_nodes(root / relative, entry)
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(root / relative), "exec",
                         flags=__future__.annotations.compiler_flag), namespace)
            if relative.endswith("reasons.py"):
                reasons = namespace["ShadowReason"]
            elif relative.endswith("signals.py"):
                self._signal = namespace["signal_from_arrays"]
            elif relative.endswith("original.py"):
                self.hybrid_family = namespace["hybrid_family"]
                self.select_argmax = namespace["select_name_argmax"]
            elif relative.endswith("ai_ensemble.py"):
                self.ai = namespace["AIEnsemble"]()
                self.quant_stub = namespace["_quant_stub_vote"]
            elif relative.endswith("rl_agent.py"):
                self.rl = namespace["RLAgent"]()
            elif relative.endswith("profit_protection.py"):
                self.protection = namespace["apply_profit_protection"]
            elif relative.endswith('/trading.py'):
                self.entry_distances=namespace['sl_tp_distance_for_entry']

    def signal(self, strategy, i, pack):
        if not all(math.isfinite(pack[k][i]) for k in (
                "close", "ma_fast", "ma_slow", "atr", "boll_up", "boll_down")):
            return None, "WARMUP_OR_NONFINITE"
        return self._signal(strategy, i, pack)

    def availability(self):
        coroutine = self.ai.vote({}, "EUR_USD")
        try:
            coroutine.send(None)
        except StopIteration as finished:
            ai = finished.value
        else:
            coroutine.close()
            raise ResearchRejected("unexpected_async_io")
        return {"ai": ai, "rl": self.rl.decide("study"), "quant_stub": self.quant_stub({}),
                "model_artifact": "UNAVAILABLE: no fold-bound verified model loaded",
                "calibrated_probabilities": False}
