"""Bounded forensic traces. No trade simulation, no signal-generation replay."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.csv_ohlcv import load_ohlcv_csv
from forex_bot.indicators import compute_indicators

SYMBOLS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
DATA_DIR = Path("data/historical")
EPS = 1e-6
MOM_THR = 0.0001
FIXED_INDICES = (5000, 15000, 25000, 40000, 60000)
FREQ_START = 8000
FREQ_BARS = 4000


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_symbol(symbol: str) -> pd.DataFrame:
    path = DATA_DIR / f"{symbol}_M5.csv"
    df = load_ohlcv_csv(path)
    return df.reset_index(drop=True)


def periods(lookback: int, n: int) -> tuple[int, int]:
    lb = max(20, min(int(lookback), max(n, 20)))
    cap = n - 1
    ma_fast_n = max(3, min(lb // 10, cap))
    ma_slow_n = max(ma_fast_n + 1, min(lb // 2, cap))
    return ma_fast_n, ma_slow_n


def features_at(ind: pd.DataFrame, i: int) -> dict:
    last = ind.iloc[i]
    price = float(last["close"])
    ma_f = last["ma_fast"]
    ma_s = last["ma_slow"]
    ma_fast = float(ma_f) if ma_f == ma_f else price
    ma_slow = float(ma_s) if ma_s == ma_s else price
    atr_v = last["atr"]
    atr = float(atr_v) if atr_v == atr_v else 0.0
    ret_1 = float(ind["close"].pct_change().iloc[i]) if i > 0 else 0.0
    vote = _quant_stub_vote(
        {"price": price, "ma_fast": ma_fast, "ma_slow": ma_slow, "returns": ret_1, "atr": atr}
    )
    ma_dir = "BUY" if ma_fast > ma_slow + EPS else ("SELL" if ma_fast < ma_slow - EPS else "FLAT")
    mom_dir = "BUY" if ret_1 > MOM_THR else ("SELL" if ret_1 < -MOM_THR else "WEAK")
    mom_sign = "BUY" if ret_1 > 0 else ("SELL" if ret_1 < 0 else "FLAT")
    return {
        "i": i,
        "time": str(ind["time"].iloc[i]),
        "close": price,
        "prev_close": float(ind["close"].iloc[i - 1]) if i else None,
        "ma_fast": ma_fast,
        "ma_slow": ma_slow,
        "ma_diff": ma_fast - ma_slow,
        "atr": atr,
        "ret_1": ret_1,
        "ma_dir": ma_dir,
        "mom_sign": mom_sign,
        "mom_gate": mom_dir,
        "agree": ma_dir == mom_sign and ma_dir in ("BUY", "SELL"),
        "direction": vote.get("direction"),
        "allow": bool(vote.get("allow")),
        "confidence": vote.get("confidence"),
    }


def independent_sma(closes: pd.Series, n: int, i: int) -> float:
    window = closes.iloc[i - n + 1 : i + 1]
    assert len(window) == n
    return float(window.mean())


def run_lengths(sides: list[str]) -> dict:
    if not sides:
        return {"n_runs": 0, "median": None, "p90": None, "max": None, "mean": None}
    runs = []
    cur = sides[0]
    length = 1
    for s in sides[1:]:
        if s == cur:
            length += 1
        else:
            runs.append(length)
            cur = s
            length = 1
    runs.append(length)
    ser = pd.Series(runs)
    return {
        "n_runs": int(len(runs)),
        "mean": float(ser.mean()),
        "median": float(ser.median()),
        "p90": float(ser.quantile(0.90)),
        "max": int(ser.max()),
    }


def main() -> None:
    print("START", utc_now())
    traces = []
    freq_rows = []
    sign_checks = []
    align_rows = []

    for symbol in SYMBOLS:
        df = load_symbol(symbol)
        n = len(df)
        lookback = 50 if symbol == "USD_JPY" else 100
        print(f"\n=== {symbol} bars={n} lookback={lookback} ===")
        ind = compute_indicators(df, lookback=lookback)
        fast_n, slow_n = periods(lookback, n)

        # Independent SMA check at a mid-file index
        chk_i = 15000
        man_fast = independent_sma(df["close"], fast_n, chk_i)
        man_slow = independent_sma(df["close"], slow_n, chk_i)
        impl_fast = float(ind["ma_fast"].iloc[chk_i])
        impl_slow = float(ind["ma_slow"].iloc[chk_i])
        sign_checks.append(
            {
                "symbol": symbol,
                "i": chk_i,
                "fast_n": fast_n,
                "slow_n": slow_n,
                "man_fast": man_fast,
                "impl_fast": impl_fast,
                "fast_delta": man_fast - impl_fast,
                "man_slow": man_slow,
                "impl_slow": impl_slow,
                "slow_delta": man_slow - impl_slow,
            }
        )
        print(
            f"INDEPENDENT SMA i={chk_i} fast_n={fast_n} delta={man_fast-impl_fast:.12e} "
            f"slow_n={slow_n} delta={man_slow-impl_slow:.12e}"
        )

        # Alignment: last included bar time == evaluation time
        feat = features_at(ind, chk_i)
        align_rows.append(
            {
                "symbol": symbol,
                "eval_time": feat["time"],
                "last_close_used": feat["close"],
                "bar_i_time": str(df["time"].iloc[chk_i]),
                "bar_i_plus_1_time": str(df["time"].iloc[chk_i + 1]),
                "uses_future_close": feat["close"] == float(df["close"].iloc[chk_i + 1]),
            }
        )

        # Fixed traces
        for i in FIXED_INDICES:
            if i >= n:
                continue
            row = features_at(ind, i)
            row["symbol"] = symbol
            row["lookback"] = lookback
            traces.append(row)
            print(
                f"TRACE {symbol} i={i} t={row['time']} close={row['close']:.6f} "
                f"MAf={row['ma_fast']:.6f} MAs={row['ma_slow']:.6f} diff={row['ma_diff']:.6g} "
                f"ret={row['ret_1']:.6g} atr={row['atr']:.6g} "
                f"MA={row['ma_dir']} MOM={row['mom_sign']} agree={row['agree']} "
                f"vote={row['direction']} allow={row['allow']}"
            )

        # Hunt disagreement / near-threshold / vol extremes in a 4000-bar window
        start = FREQ_START
        end = min(n, start + FREQ_BARS)
        window = []
        for i in range(start, end):
            window.append(features_at(ind, i))
        disagree = [r for r in window if r["direction"] in ("BUY", "SELL") and not r["agree"] and r["allow"]]
        near = [r for r in window if r["direction"] is None or abs(r["ma_diff"]) < 5e-5]
        atr_s = pd.Series([r["atr"] for r in window])
        atr_hi = float(atr_s.quantile(0.95))
        atr_lo = float(atr_s.quantile(0.05))
        hi_vol = next((r for r in window if r["atr"] >= atr_hi and r["allow"]), None)
        lo_vol = next((r for r in window if r["atr"] <= atr_lo), None)
        print(f"WINDOW {start}:{end} disagree_allow={len(disagree)} near_flat={len(near)}")
        if disagree:
            d = disagree[0]
            d["symbol"] = symbol
            d["lookback"] = lookback
            d["tag"] = "DISAGREE"
            traces.append(d)
            print(
                f"DISAGREE {symbol} t={d['time']} MA={d['ma_dir']} MOM={d['mom_sign']} "
                f"vote={d['direction']} ret={d['ret_1']:.6g}"
            )
        if near:
            d = min(near, key=lambda r: abs(r["ma_diff"]))
            print(f"NEAR {symbol} t={d['time']} diff={d['ma_diff']:.6g} vote={d['direction']} allow={d['allow']}")
        if hi_vol:
            print(f"HIVOL {symbol} t={hi_vol['time']} atr={hi_vol['atr']:.6g} vote={hi_vol['direction']}")
        if lo_vol:
            print(f"LOVOL {symbol} t={lo_vol['time']} atr={lo_vol['atr']:.6g} vote={lo_vol['direction']} allow={lo_vol['allow']}")

        # Frequency: direction always vs allow
        dirs = [r["direction"] if r["direction"] in ("BUY", "SELL") else "NONE" for r in window]
        allowed = [r for r in window if r["allow"] and r["direction"] in ("BUY", "SELL")]
        c = Counter(dirs)
        ac = Counter(r["direction"] for r in allowed)
        agree_n = sum(1 for r in allowed if r["agree"])
        sides = [r["direction"] for r in window if r["direction"] in ("BUY", "SELL")]
        runs = run_lengths(sides)
        allow_sides = [r["direction"] for r in allowed]
        allow_runs = run_lengths(allow_sides)
        freq_rows.append(
            {
                "symbol": symbol,
                "lookback": lookback,
                "n": len(window),
                "dir_buy": c.get("BUY", 0),
                "dir_sell": c.get("SELL", 0),
                "dir_none": c.get("NONE", 0),
                "allow_buy": ac.get("BUY", 0),
                "allow_sell": ac.get("SELL", 0),
                "allow_n": len(allowed),
                "allow_frac": len(allowed) / len(window) if window else 0,
                "allow_agree_frac": (agree_n / len(allowed)) if allowed else 0,
                "dir_run_median": runs["median"],
                "dir_run_p90": runs["p90"],
                "dir_run_max": runs["max"],
                "dir_run_mean": runs["mean"],
                "allow_run_median": allow_runs["median"],
                "allow_run_max": allow_runs["max"],
            }
        )
        print(
            f"FREQ n={len(window)} dir B/S/N={c.get('BUY',0)}/{c.get('SELL',0)}/{c.get('NONE',0)} "
            f"allow={len(allowed)} ({len(allowed)/len(window):.3f}) "
            f"allow_agree={agree_n/len(allowed) if allowed else 0:.3f} "
            f"dir_run med={runs['median']} p90={runs['p90']} max={runs['max']}"
        )

        # Swing lookback frequency for non-JPY (diagnostic only)
        if symbol != "USD_JPY":
            ind2 = compute_indicators(df, lookback=200)
            w2 = [features_at(ind2, i) for i in range(start, end)]
            allowed2 = [r for r in w2 if r["allow"] and r["direction"] in ("BUY", "SELL")]
            sides2 = [r["direction"] for r in w2 if r["direction"] in ("BUY", "SELL")]
            runs2 = run_lengths(sides2)
            c2 = Counter(r["direction"] if r["direction"] in ("BUY", "SELL") else "NONE" for r in w2)
            print(
                f"FREQ_SWING200 dir B/S/N={c2.get('BUY',0)}/{c2.get('SELL',0)}/{c2.get('NONE',0)} "
                f"allow={len(allowed2)} dir_run med={runs2['median']} max={runs2['max']}"
            )

    print("\n=== SIGN / SMA RECOMPUTE ===")
    for r in sign_checks:
        print(r)

    print("\n=== ALIGNMENT ===")
    for r in align_rows:
        print(r)

    print("\n=== FREQ TABLE ===")
    print(pd.DataFrame(freq_rows).to_string(index=False))
    print("FINISH", utc_now())


if __name__ == "__main__":
    main()
