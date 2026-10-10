"""Post-hoc Stage E diagnostics. Exploratory. Does not retune rules."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from forex_bot.shadow.classify import classify_strategy, overall_decision
from forex_bot.shadow.reasons import STRATEGY_NAMES


def _cell(blob: dict[str, Any], period: str, scenario: str, strategy: str) -> dict[str, Any]:
    cells = blob["isolated"][period][scenario]["cells"]
    closes = 0
    net = 0.0
    costs = 0.0
    dd = 0.0
    wins = 0
    by_pair: dict[str, dict[str, Any]] = {}
    exit_reasons: dict[str, int] = defaultdict(int)
    rejects: dict[str, int] = defaultdict(int)
    size_infeasible = 0
    hold: list[float] = []
    ci_lo: float | None = None
    ci_hi: float | None = None
    gross_win = 0.0
    gross_loss = 0.0
    for key, stats in cells.items():
        name, pair = key.split("|", 1)
        if name != strategy:
            continue
        n = int(stats.get("closes") or 0)
        closes += n
        net += float(stats.get("net_gbp") or 0.0)
        costs += float(stats.get("costs_gbp") or 0.0)
        dd = max(dd, float(stats.get("max_dd_gbp") or 0.0))
        size_infeasible += int(stats.get("size_infeasible") or 0)
        by_pair[pair] = {
            "n": n,
            "net": float(stats.get("net_gbp") or 0.0),
            "win_rate": stats.get("win_rate"),
        }
        for reason, cnt in (stats.get("exit_reasons") or {}).items():
            exit_reasons[reason] += int(cnt)
        for reason, cnt in (stats.get("signals_or_traces") or {}).items():
            rejects[reason] += int(cnt)
        if stats.get("avg_hold_seconds") is not None:
            hold.append(float(stats["avg_hold_seconds"]))
        unc = stats.get("uncertainty") or {}
        if unc.get("ci95"):
            lo, hi = float(unc["ci95"][0]), float(unc["ci95"][1])
            ci_lo = lo if ci_lo is None else ci_lo + lo
            ci_hi = hi if ci_hi is None else ci_hi + hi
        wr = stats.get("win_rate")
        n_win = 0
        if wr is not None and n:
            n_win = round(float(wr) * n)
            wins += n_win
        aw = stats.get("avg_win")
        al = stats.get("avg_loss")
        if n_win and aw is not None:
            gross_win += float(aw) * n_win
        n_loss = n - n_win
        if n_loss and al is not None:
            gross_loss += abs(float(al)) * n_loss
    return {
        "closes": closes,
        "net": net,
        "costs": costs,
        "dd": dd,
        "wins": wins,
        "by_pair": by_pair,
        "exit_reasons": exit_reasons,
        "rejects": rejects,
        "size_infeasible": size_infeasible,
        "hold": hold,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "gross_win": gross_win,
        "gross_loss": gross_loss,
    }


def summarise(blob: dict[str, Any]) -> dict[str, Any]:
    strategies: dict[str, Any] = {}
    for name in STRATEGY_NAMES:
        ho = _cell(blob, "heldout", "base", name)
        cons = _cell(blob, "heldout", "conservative", name)
        sev = _cell(blob, "heldout", "severe", name)
        val = _cell(blob, "validation", "base", name)
        dev = _cell(blob, "development", "base", name)
        pair_nets = {p: d["net"] for p, d in ho["by_pair"].items()}
        total = sum(pair_nets.values()) if pair_nets else 0.0
        top_share = 0.0
        if pair_nets and abs(total) > 1e-12:
            top_share = max(abs(v) for v in pair_nets.values()) / sum(abs(v) for v in pair_nets.values())
        port = blob["portfolio"]["heldout"]["base"]
        row = {
            "heldout_n": ho["closes"],
            "heldout_net": ho["net"],
            "heldout_pf": (ho["gross_win"] / ho["gross_loss"]) if ho["gross_loss"] > 1e-12 else None,
            "heldout_dd": ho["dd"],
            "cons_net": cons["net"],
            "severe_net": sev["net"],
            "val_net": val["net"],
            "dev_net": dev["net"],
            "ci_lo": ho["ci_lo"],
            "ci_hi": ho["ci_hi"],
            "top_pair_share": top_share,
        }
        wins = ho["wins"]
        wr = (wins / ho["closes"]) if ho["closes"] else None
        cls = classify_strategy(row)
        port_strat = (port.get("by_strategy") or {}).get(name) or {}
        strategies[name] = {
            "classification": cls,
            "heldout_isolated": {
                "closes": ho["closes"],
                "net_gbp": ho["net"],
                "costs_gbp": ho["costs"],
                "profit_factor": row["heldout_pf"],
                "max_dd_gbp": ho["dd"],
                "win_rate": wr,
                "by_pair": ho["by_pair"],
                "exit_reasons": dict(ho["exit_reasons"]),
                "size_infeasible": ho["size_infeasible"],
            },
            "heldout_conservative_net": cons["net"],
            "heldout_severe_net": sev["net"],
            "validation_net": val["net"],
            "development_net": dev["net"],
            "portfolio_heldout_base": port_strat,
            "top_pair_share": top_share,
            "label": "EXPERIMENTAL_HEURISTIC_OFFLINE",
        }
    decision = overall_decision(
        {k: v["classification"] for k, v in strategies.items()},
        simulator_ok=True,
        data_ok=True,
    )
    return {
        "label": "EXPERIMENTAL_HEURISTIC_OFFLINE",
        "not_original_bot": True,
        "strategies": strategies,
        "portfolio_heldout": {
            scenario: blob["portfolio"]["heldout"][scenario]
            for scenario in ("base", "conservative", "severe")
        },
        "overall_decision": decision,
        "exploratory": True,
    }


def write_diagnosis(results_path: Path, dest: Path) -> dict[str, Any]:
    blob = json.loads(results_path.read_text(encoding="utf-8"))
    out = summarise(blob)
    dest.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out
