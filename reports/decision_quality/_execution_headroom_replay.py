"""Offline-only replay of execution-headroom policies.

Does not import production trading loop. Does not call OANDA. Reads the
already-written forensic JSON from the STOP_LOSS_ON_FILL_LOSS audit.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "_sl_on_fill_analysis.json"
OUT = ROOT / "_execution_headroom_replay.json"


def pip_size(symbol: str) -> float:
    return 0.01 if "JPY" in (symbol or "").upper() else 0.0001


def tick_size(symbol: str) -> float:
    return 0.001 if "JPY" in (symbol or "").upper() else 0.00001


def trigger_side(side: str) -> str:
    return "bid" if (side or "").upper() == "BUY" else "ask"


def trigger_price(side: str, bid: float, ask: float) -> float:
    return float(bid) if (side or "").upper() == "BUY" else float(ask)


def clearance(side: str, sl: float, bid: float, ask: float) -> float:
    """Positive => intended SL is strictly inside the trigger side."""
    if (side or "").upper() == "BUY":
        return float(bid) - float(sl)
    return float(sl) - float(ask)


def pctile(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    k = (len(ys) - 1) * p
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return ys[lo]
    w = k - lo
    return ys[lo] * (1.0 - w) + ys[hi] * w


def dist(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "min": min(xs),
        "p10": pctile(xs, 0.10),
        "p25": pctile(xs, 0.25),
        "median": pctile(xs, 0.50),
        "p75": pctile(xs, 0.75),
        "max": max(xs),
    }


def policy_a(cl: float) -> str:
    return "SKIP" if cl <= 0 else "SUBMIT"


def policy_e(stop_d: float, spread: float) -> str:
    return "SKIP" if stop_d <= spread else "SUBMIT"


def policy_c_d(side: str, sl: float, tp: float, xref: float, bid: float, ask: float, symbol: str) -> dict:
    pip = pip_size(symbol)
    tick = tick_size(symbol)
    cl = clearance(side, sl, bid, ask)
    side_u = (side or "").upper()
    if cl > 0:
        return {
            "would_modify": False,
            "sl_new": sl,
            "tp_c": tp,
            "tp_d": tp,
            "new_r_c": None,
            "new_risk_pips": abs(xref - sl) / pip,
            "risk_mult": 1.0,
        }
    if side_u == "BUY":
        sl_new = float(bid) - tick
        risk_c = float(xref) - sl_new
        reward_c = float(tp) - float(xref)
        tp_d = float(xref) + 2.0 * risk_c
    else:
        sl_new = float(ask) + tick
        risk_c = sl_new - float(xref)
        reward_c = float(xref) - float(tp)
        tp_d = float(xref) - 2.0 * risk_c
    old_risk = abs(float(xref) - float(sl))
    return {
        "would_modify": True,
        "sl_new": sl_new,
        "tp_c": tp,
        "tp_d": tp_d,
        "new_r_c": (reward_c / risk_c) if risk_c > 0 else None,
        "new_risk_pips": risk_c / pip,
        "old_risk_pips": old_risk / pip,
        "risk_mult": (risk_c / old_risk) if old_risk > 0 else None,
        "tp_move_pips": abs(tp_d - tp) / pip,
    }


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    cancelled_rows = []
    for ev in data["cancelled"]:
        symbol = ev["instrument"]
        side = ev["side"]
        sl = float(ev["sl"])
        tp = float(ev["tp"])
        xref = float(ev["implied_xref"])
        sl_d = float(ev["implied_sl_d"])
        bid = float(ev["m1_bid_c"])
        ask = float(ev["m1_ask_c"])
        spread = float(ev["m1_spread"])
        pip = pip_size(symbol)
        cl = clearance(side, sl, bid, ask)
        sl_d_minus_spread = sl_d - spread
        a = policy_a(cl)
        e = policy_e(sl_d, spread)
        cd = policy_c_d(side, sl, tp, xref, bid, ask, symbol)
        cancelled_rows.append(
            {
                "cid": ev["cid"],
                "symbol": symbol,
                "side": side,
                "sl": sl,
                "tp": tp,
                "xref": xref,
                "bid": bid,
                "ask": ask,
                "spread_pips": spread / pip,
                "stop_pips": sl_d / pip,
                "clearance": cl,
                "clearance_pips": cl / pip,
                "clearance_over_stop": cl / sl_d if sl_d else None,
                "clearance_over_spread": cl / spread if spread else None,
                "unrounded_sl_d_minus_spread_pips": sl_d_minus_spread / pip,
                "policy_a": a,
                "policy_b": "SUBMIT",
                "policy_e": e,
                "a_vs_e": a == e,
                "policy_c_d": cd,
                "actual": "STOP_LOSS_ON_FILL_LOSS",
            }
        )

    success_rows = []
    for ev in data["successful"]:
        symbol = ev["instrument"]
        side = ev["side"]
        sl = float(ev["sl"])
        tp = float(ev["tp"])
        xref = float(ev["xref"])
        fill = float(ev["fill"])
        bid = float(ev["m1_bid_c"])
        ask = float(ev["m1_ask_c"])
        pip = pip_size(symbol)
        sl_d = abs(xref - sl)
        spread = ask - bid
        cl = clearance(side, sl, bid, ask)
        a = policy_a(cl)
        e = policy_e(sl_d, spread)
        success_rows.append(
            {
                "cid": ev["cid"],
                "symbol": symbol,
                "side": side,
                "sl": sl,
                "tp": tp,
                "xref": xref,
                "fill": fill,
                "bid": bid,
                "ask": ask,
                "spread_pips": spread / pip,
                "stop_pips": sl_d / pip,
                "clearance": cl,
                "clearance_pips": cl / pip,
                "clearance_over_stop": cl / sl_d if sl_d else None,
                "unrounded_sl_d_minus_spread_pips": (sl_d - spread) / pip,
                "policy_a": a,
                "policy_b": "SUBMIT",
                "policy_e": e,
                "a_vs_e": a == e,
                "actual": "FILLED",
            }
        )

    cancel_cl = [r["clearance_pips"] for r in cancelled_rows]
    succ_cl = [r["clearance_pips"] for r in success_rows]
    a_block_cancels = sum(1 for r in cancelled_rows if r["policy_a"] == "SKIP")
    a_allow_success = sum(1 for r in success_rows if r["policy_a"] == "SUBMIT")
    e_block_cancels = sum(1 for r in cancelled_rows if r["policy_e"] == "SKIP")
    e_allow_success = sum(1 for r in success_rows if r["policy_e"] == "SUBMIT")
    a_e_agree = all(r["a_vs_e"] for r in cancelled_rows + success_rows)

    buffers = {}
    for name, req in [("exact_gt_0", 0.0), ("0.1_pip", 0.1), ("0.5_pip", 0.5), ("1.0_pip", 1.0), ("10pct_stop", None)]:
        c_skip = 0
        s_skip = 0
        for r in cancelled_rows:
            req_p = 0.1 * r["stop_pips"] if name == "10pct_stop" else req
            if r["clearance_pips"] <= req_p:
                c_skip += 1
        for r in success_rows:
            req_p = 0.1 * r["stop_pips"] if name == "10pct_stop" else req
            if r["clearance_pips"] <= req_p:
                s_skip += 1
        buffers[name] = {
            "cancels_blocked": c_skip,
            "successful_false_skips": s_skip,
        }

    c_r = [r["policy_c_d"]["new_r_c"] for r in cancelled_rows if r["policy_c_d"]["new_r_c"] is not None]
    c_mult = [r["policy_c_d"]["risk_mult"] for r in cancelled_rows if r["policy_c_d"]["risk_mult"] is not None]
    d_tp = [r["policy_c_d"]["tp_move_pips"] for r in cancelled_rows if r["policy_c_d"].get("tp_move_pips") is not None]

    out = {
        "book_proxy": "M1 MBA completed-bar close (not persisted PricingInfo)",
        "n_cancelled": len(cancelled_rows),
        "n_successful": len(success_rows),
        "n_expanded_reliable": len(cancelled_rows) + len(success_rows),
        "policy_a": {
            "cancels_prevented": a_block_cancels,
            "successful_allowed": a_allow_success,
            "false_skips": len(success_rows) - a_allow_success,
            "false_allows": len(cancelled_rows) - a_block_cancels,
            "true_blocks": a_block_cancels,
            "true_allows": a_allow_success,
        },
        "policy_e": {
            "cancels_prevented": e_block_cancels,
            "successful_allowed": e_allow_success,
            "false_skips": len(success_rows) - e_allow_success,
            "a_e_agree_on_all_events": a_e_agree,
        },
        "clearance_pips_cancelled": dist(cancel_cl),
        "clearance_pips_successful": dist(succ_cl),
        "cancels_with_positive_clearance": sum(1 for x in cancel_cl if x > 0),
        "fills_with_nonpositive_clearance": sum(1 for x in succ_cl if x <= 0),
        "policy_c_new_r_cancelled": dist(c_r),
        "policy_c_risk_multiple_cancelled": dist(c_mult),
        "policy_d_tp_move_pips_cancelled": dist(d_tp),
        "buffer_candidates": buffers,
        "cancelled": cancelled_rows,
        "successful": success_rows,
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("A cancels", a_block_cancels, "/", len(cancelled_rows))
    print("A success allowed", a_allow_success, "/", len(success_rows))
    print("A false skips", len(success_rows) - a_allow_success)
    print("A vs E agree", a_e_agree)
    print("cancel clearance", dist(cancel_cl))
    print("success clearance", dist(succ_cl))
    print("buffers", buffers)
    print("policy C R", dist(c_r))
    print("policy C risk mult", dist(c_mult))
    print("policy D TP move pips", dist(d_tp))


if __name__ == "__main__":
    main()
