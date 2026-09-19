"""Read-only forensic helpers for the quant stub. Does not change production."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.indicators import compute_indicators
from forex_bot.csv_ohlcv import load_ohlcv_csv

SYMBOLS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
DATA_DIR = Path("data/historical")
EPS = 1e-6
MOM_THR = 0.0001


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def env_keys() -> dict[str, str]:
    keys = (
        "ENSEMBLE_MODE",
        "AI_DISABLE_STUB",
        "STUB_SMA_EPSILON",
        "STUB_MOMENTUM_THRESHOLD",
        "STUB_CONFIDENCE_SCALE",
        "SCALP_LOOKBACK",
        "SWING_LOOKBACK",
        "DEFAULT_INDICATOR_LOOKBACK",
        "HYBRID_ROUTE_LOOKBACK",
        "HYBRID_EUR_USD",
        "HYBRID_GBP_USD",
        "HYBRID_USD_JPY",
        "HYBRID_AUD_USD",
        "HYBRID_USD_CAD",
        "HYBRID_USD_CHF",
        "HYBRID_ATR_SCALP_THRESHOLD",
        "NN_PRED_MODE",
        "FOREX_BACKTEST",
    )
    p = Path(".env")
    vals: dict[str, str] = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            if k in keys:
                vals[k] = v
    return {k: vals.get(k, "<UNSET>") for k in keys}


def ma_periods(lookback: int, n: int) -> tuple[int, int, int]:
    lb = max(20, min(int(lookback), max(n, 20)))
    cap = min(n - 1, n - 1)
    ma_fast_n = max(3, min(lb // 10, cap))
    ma_slow_n = max(ma_fast_n + 1, min(lb // 2, cap))
    atr_n = max(7, min(lb // 5, min(30, cap)))
    return ma_fast_n, ma_slow_n, atr_n


def vote_row(ind, i: int) -> dict:
    last = ind.iloc[i]
    price = float(last["close"])
    ma_fast = float(last["ma_fast"]) if last["ma_fast"] == last["ma_fast"] else price
    ma_slow = float(last["ma_slow"]) if last["ma_slow"] == last["ma_slow"] else price
    atr = float(last["atr"]) if last["atr"] == last["atr"] else 0.0
    ret_1 = float(ind["close"].pct_change().iloc[i]) if i > 0 else 0.0
    vote = _quant_stub_vote(
        {"price": price, "ma_fast": ma_fast, "ma_slow": ma_slow, "returns": ret_1, "atr": atr}
    )
    ma_dir = "BUY" if ma_fast > ma_slow + EPS else ("SELL" if ma_fast < ma_slow - EPS else "FLAT")
    mom_dir = "BUY" if ret_1 > 0 else ("SELL" if ret_1 < 0 else "FLAT")
    agree = ma_dir == mom_dir and ma_dir in ("BUY", "SELL")
    return {
        "price": price,
        "ma_fast": ma_fast,
        "ma_slow": ma_slow,
        "ma_diff": ma_fast - ma_slow,
        "atr": atr,
        "ret_1": ret_1,
        "ma_dir": ma_dir,
        "mom_dir": mom_dir,
        "agree": agree,
        "direction": vote.get("direction"),
        "allow": vote.get("allow"),
        "confidence": vote.get("confidence"),
    }


def print_env() -> None:
    for k, v in env_keys().items():
        print(f"{k}={v}")


if __name__ == "__main__":
    print("UTC", utc_now())
    print_env()
    for lb in (50, 100, 200):
        f, s, a = ma_periods(lb, 10000)
        print(f"lookback={lb} ma_fast_n={f} ma_slow_n={s} atr_n={a}")
