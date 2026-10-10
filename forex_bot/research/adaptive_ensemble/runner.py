"""Write Stage G artifacts. Offline only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble import LABEL
from forex_bot.research.adaptive_ensemble.audit import inventory
from forex_bot.research.adaptive_ensemble.evaluate import (
    evaluate_frame,
    split_bounds,
    write_report,
)
from forex_bot.research.adaptive_ensemble.features import (
    FEATURE_CATALOG,
    compute_feature_frame,
)
from forex_bot.research.adaptive_ensemble.protocol import DEFAULT_PATH, write_protocol
from forex_bot.research.adaptive_ensemble.simulate import (
    fill_price,
    mark_exit,
    quote_to_gbp,
)

OUT = Path("data") / "research" / "adaptive_ensemble"
EUR = Path("data") / "historical" / "EUR_USD_M5.csv"


def synthetic_market(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = np.cumsum(rng.normal(0.00002, 0.0004, n)) + 1.10
    high = close + np.abs(rng.normal(0.0002, 0.0001, n))
    low = close - np.abs(rng.normal(0.0002, 0.0001, n))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    times = pd.date_range("2024-01-02", periods=n, freq="5min", tz="UTC")
    spread = 0.00012
    frame = pd.DataFrame(
        {
            "time": times,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "bid_open": open_ - spread / 2,
            "ask_open": open_ + spread / 2,
            "bid_close": close - spread / 2,
            "ask_close": close + spread / 2,
        }
    )
    from forex_bot.market_provenance import bind_synthetic_frame

    return bind_synthetic_frame(frame)


def accounting_fixture() -> dict[str, Any]:
    df = synthetic_market(120)
    from forex_bot.research.adaptive_ensemble.features import compute_feature_frame

    feat = compute_feature_frame(df)
    entry = fill_price(feat, 90, "BUY", "base")
    if entry is None:
        raise RuntimeError("accounting fixture missing fill")
    atr = float(feat.iloc[89]["feat_atr"])
    sl = entry - 1.5 * atr
    tp = entry + 2.0 * atr
    exit_i, exit_px, why = mark_exit(feat, 90, "BUY", entry, sl, tp, 24)
    pnl_q = (exit_px - entry) * 1000.0
    pnl_g = quote_to_gbp(pnl_q, "EUR_USD", 1.35)
    return {
        "entry": entry,
        "exit_i": exit_i,
        "exit_px": exit_px,
        "why": why,
        "pnl_quote": pnl_q,
        "pnl_gbp": pnl_g,
        "reconcile_ok": abs(pnl_g - pnl_q / 1.35) < 1e-9,
    }


def run(out: Path | None = None) -> dict[str, Any]:
    dest = out or OUT
    dest.mkdir(parents=True, exist_ok=True)
    proto = write_protocol(dest / "protocol_v1.json" if out else DEFAULT_PATH)
    inv = inventory()
    (dest / "data_inventory.json").write_text(json.dumps(inv, indent=2, sort_keys=True), encoding="utf-8")
    (dest / "feature_catalog.json").write_text(
        json.dumps(FEATURE_CATALOG, indent=2, sort_keys=True), encoding="utf-8"
    )
    syn = synthetic_market(360)
    syn_feat = compute_feature_frame(syn)
    syn_res = {
        c: evaluate_frame(
            syn, pair="EUR_USD", cost=c, lo=80, hi=len(syn) - 2, work=dest, precomputed=syn_feat
        )
        for c in ("base", "conservative", "severe", "ablation_no_cost_filter")
    }
    hist: dict[str, Any] = {"status": "UNAVAILABLE", "reason": "EUR_USD_M5.csv missing"}
    if EUR.is_file():
        raw = pd.read_csv(EUR)
        n = len(raw)
        _d0, _d1, val_end = split_bounds(n)
        remainder_lo = val_end
        feat = compute_feature_frame(raw)
        hist = {
            "status": "PREVIOUSLY_EXAMINED_EXPLORATORY",
            "genuine_fresh_holdout": False,
            "rows": n,
            "remainder_lo": remainder_lo,
            "remainder_hi": n - 2,
            "costs": {},
        }
        for c in ("base", "conservative", "severe"):
            hist["costs"][c] = evaluate_frame(
                raw,
                pair="EUR_USD",
                cost=c,
                lo=remainder_lo,
                hi=n - 2,
                work=dest,
                precomputed=feat,
            )
    payload = {
        "label": LABEL,
        "protocol_id": proto["protocol_id"],
        "protocol_version": proto["version"],
        "integrity_hash": proto["integrity_hash"],
        "frozen_utc": proto["frozen_utc"],
        "accounting_fixture": accounting_fixture(),
        "synthetic": syn_res,
        "historical_eur_usd": hist,
        "assessment_note": "Do not treat Sep 2025–Aug 2026 as unseen.",
    }
    write_report(dest / "evaluation_results.json", payload)
    return payload


if __name__ == "__main__":
    run()
