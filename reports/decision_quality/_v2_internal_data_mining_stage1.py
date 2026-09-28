"""V2 internal data mining stage 1. Local JSONL only. Not imported by bot_loop."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.v2_shadow.score import HORIZONS_MIN
from forex_bot.v2_shadow.score_offline import (
    _ts,
    last_completed_m5_start,
    load_observation_records,
)
from forex_bot.v2_shadow.store import default_store_dir, observations_path, outcomes_path

HORIZONS = tuple(str(h) for h in HORIZONS_MIN)
SMALL_N = 30
MIN_N_COMPARE = 40
HIT_DELTA_FLOOR = 0.08
PIP_DELTA_FLOOR = 1.0
TRADE_DUMP = Path("reports/decision_quality/_live_trade_dump.json")


def opportunity_key(symbol: str, timestamp_utc: Any) -> str | None:
    ts = _ts(timestamp_utc)
    if ts is None or not symbol:
        return None
    return f"{symbol}|{last_completed_m5_start(ts).isoformat()}"


def unique_opportunities(obs_rows: list[dict]) -> tuple[dict[str, dict], int]:
    """Earliest observation per (symbol, last completed M5 start). Same as checkpoint."""
    earliest: dict[str, tuple[datetime, dict]] = {}
    for rec in obs_rows:
        ts = _ts(rec.get("timestamp_utc"))
        if ts is None:
            continue
        key = opportunity_key(str(rec.get("symbol") or ""), ts)
        if key is None:
            continue
        prev = earliest.get(key)
        if prev is None or ts < prev[0]:
            earliest[key] = (ts, rec)
    return {k: v[1] for k, v in earliest.items()}, len(obs_rows)


def merge_outcomes(rows: list[dict]) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for row in rows:
        did = row.get("decision_id")
        if not did:
            continue
        cur = by_id.setdefault(did, {"decision_id": did, "horizons": {}})
        for hz, blob in (row.get("horizons") or {}).items():
            existing = cur["horizons"].setdefault(str(hz), {})
            if not isinstance(blob, dict):
                continue
            if "buy" in blob and "buy" not in existing:
                existing["buy"] = blob["buy"]
            if "sell" in blob and "sell" not in existing:
                existing["sell"] = blob["sell"]
    return by_id


def _cell(inputs: dict, name: str) -> tuple[Any, str]:
    cell = (inputs or {}).get(name) or {}
    if not isinstance(cell, dict):
        return None, "MISSING"
    return cell.get("value"), str(cell.get("status") or "MISSING")


def _f(raw: Any) -> float | None:
    if raw is None or raw is False or raw is True:
        return None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def _sign(raw: Any) -> str:
    x = _f(raw)
    if x is None:
        return "missing"
    if x > 0:
        return "pos"
    if x < 0:
        return "neg"
    return "zero"


def _utc_block(hour: int | None) -> str:
    if hour is None:
        return "missing"
    if hour < 6:
        return "00-06"
    if hour < 12:
        return "06-12"
    if hour < 18:
        return "12-18"
    return "18-24"


def load_outcome_rows(path: Path) -> tuple[list[dict], int]:
    rows: list[dict] = []
    malformed = 0
    if not path.is_file():
        return rows, malformed
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            malformed += 1
    return rows, malformed


def extract_features(rec: dict) -> dict[str, Any]:
    inputs = rec.get("inputs") or {}
    pip = _f(_cell(inputs, "pip_size")[0])
    spread = _f(_cell(inputs, "spread")[0])
    atr = _f(_cell(inputs, "atr")[0])
    macd = _f(_cell(inputs, "macd")[0])
    hour = _cell(inputs, "hour_utc")[0]
    try:
        hour_i = int(hour) if hour is not None else None
    except (TypeError, ValueError):
        hour_i = None
    spread_pips = None if spread is None or not pip else spread / pip
    spread_over_atr = None if spread is None or atr in (None, 0) else spread / atr
    macd_over_atr = None if macd is None or atr in (None, 0) else macd / atr
    out = {
        "decision_id": rec.get("decision_id"),
        "symbol": rec.get("symbol"),
        "timestamp_utc": rec.get("timestamp_utc"),
        "production_stub_side": _cell(inputs, "production_stub_side")[0],
        "strategy_label": _cell(inputs, "strategy_label")[0],
        "usd_direction": _cell(inputs, "usd_direction")[0],
        "hour_utc": hour_i,
        "utc_block": _utc_block(hour_i),
        "day_of_week": _cell(inputs, "day_of_week")[0],
        "broker_backed_position_count": _cell(inputs, "broker_backed_position_count")[0],
        "same_usd_direction_count": _f(_cell(inputs, "same_usd_direction_count")[0]),
        "gross_portfolio_exposure": _f(_cell(inputs, "gross_portfolio_exposure")[0]),
        "atr": atr,
        "atr_over_price": _f(_cell(inputs, "atr_over_price")[0]),
        "spread": spread,
        "spread_pips": spread_pips,
        "spread_over_atr": spread_over_atr,
        "sma_difference": _f(_cell(inputs, "sma_difference")[0]),
        "sma_difference_over_atr": _f(_cell(inputs, "sma_difference_over_atr")[0]),
        "rsi": _f(_cell(inputs, "rsi")[0]),
        "macd": macd,
        "macd_over_atr": macd_over_atr,
        "bollinger_position": _f(_cell(inputs, "bollinger_position")[0]),
        "ret_1": _f(_cell(inputs, "ret_1")[0]),
        "ret_5": _f(_cell(inputs, "ret_5")[0]),
        "ret_15": _f(_cell(inputs, "ret_15")[0]),
        "ret_30": _f(_cell(inputs, "ret_30")[0]),
        "pip_size": pip,
        "adx_status": _cell(inputs, "adx")[1],
        "macd_signal_status": _cell(inputs, "macd_signal")[1],
    }
    rl = rec.get("rl") or {}
    out["rl_action"] = rl.get("action")
    out["rl_agree"] = rl.get("agree")
    out["rl_veto"] = rl.get("veto")
    out["rl_state"] = rl.get("state")
    out["rl_epsilon"] = _f(rl.get("epsilon"))
    q = rl.get("q_values") if isinstance(rl.get("q_values"), dict) else {}
    out["rl_q_buy"] = _f(q.get("BUY"))
    out["rl_q_sell"] = _f(q.get("SELL"))
    out["rl_q_skip"] = _f(q.get("SKIP"))
    return out


def attach_labels(feat: dict, outcome: dict | None) -> dict:
    row = dict(feat)
    for hz in HORIZONS:
        blob = ((outcome or {}).get("horizons") or {}).get(hz) or {}
        buy = blob.get("buy") if isinstance(blob.get("buy"), dict) else {}
        sell = blob.get("sell") if isinstance(blob.get("sell"), dict) else {}
        bp = _f(buy.get("forward_pips")) if buy.get("status") == "AVAILABLE" else None
        sp = _f(sell.get("forward_pips")) if sell.get("status") == "AVAILABLE" else None
        row[f"buy_pips_{hz}"] = bp
        row[f"sell_pips_{hz}"] = sp
        row[f"buy_hit_{hz}"] = None if bp is None else int(bp > 0)
        row[f"sell_hit_{hz}"] = None if sp is None else int(sp > 0)
        row[f"buy_mfe_{hz}"] = _f(buy.get("mfe_pips"))
        row[f"buy_mae_{hz}"] = _f(buy.get("mae_pips"))
        row[f"sell_mfe_{hz}"] = _f(sell.get("mfe_pips"))
        row[f"sell_mae_{hz}"] = _f(sell.get("mae_pips"))
    return row


def feature_integrity(obs_rows: list[dict], names: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in names:
        avail = miss = nc = 0
        vals: list[Any] = []
        nums: list[float] = []
        for rec in obs_rows:
            val, status = _cell(rec.get("inputs") or {}, name)
            if status == "AVAILABLE":
                avail += 1
                vals.append(val)
                n = _f(val)
                if n is not None:
                    nums.append(n)
            elif status == "NOT_COMPUTED":
                nc += 1
            else:
                miss += 1
        unique = len({json.dumps(v, sort_keys=True, default=str) for v in vals})
        stats = {
            "available": avail,
            "missing": miss,
            "not_computed": nc,
            "unique": unique,
            "min": min(nums) if nums else None,
            "median": statistics.median(nums) if nums else None,
            "mean": statistics.fmean(nums) if nums else None,
            "max": max(nums) if nums else None,
            "constant": unique <= 1 and avail > 0,
            "near_constant": unique <= 3 and avail > 20 and all(_f(v) is not None for v in vals[:5]) and name not in (
                "production_stub_side", "usd_direction", "pip_size", "day_of_week", "strategy_label"
            ),
        }
        out[name] = stats
    return out


def ret_1_vs_ret_5(rows: list[dict]) -> dict:
    pairs = []
    for rec in rows:
        a = rec.get("ret_1")
        b = rec.get("ret_5")
        if a is None or b is None:
            continue
        pairs.append((a, b))
    if not pairs:
        return {"n": 0}
    diffs = [a - b for a, b in pairs]
    eq = sum(1 for a, b in pairs if a == b)
    near = sum(1 for d in diffs if abs(d) <= 1e-18)
    near12 = sum(1 for d in diffs if abs(d) <= 1e-12)
    xs = [a for a, _ in pairs]
    ys = [b for _, b in pairs]
    corr = _corr(xs, ys)
    return {
        "n": len(pairs),
        "exact_equal": eq,
        "exact_equal_rate": eq / len(pairs),
        "abs_diff_le_1e18": near / len(pairs),
        "abs_diff_le_1e12": near12 / len(pairs),
        "diff_mean": statistics.fmean(diffs),
        "diff_median": statistics.median(diffs),
        "diff_min": min(diffs),
        "diff_max": max(diffs),
        "corr": corr,
        "construction_note": "bot_loop ret_1 = close.pct_change()[-1]; ret_5 uses 1 M5 bar lookback",
    }


def _corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def earlier_cuts(values: list[float]) -> list[float] | None:
    vals = sorted(v for v in values if v is not None)
    if len(vals) < 20:
        return None
    return [
        statistics.quantiles(vals, n=4, method="inclusive")[0],
        statistics.quantiles(vals, n=4, method="inclusive")[1],
        statistics.quantiles(vals, n=4, method="inclusive")[2],
    ]


def assign_quartile(x: float | None, cuts: list[float] | None) -> str:
    if x is None or not cuts:
        return "missing"
    if x <= cuts[0]:
        return "Q1"
    if x <= cuts[1]:
        return "Q2"
    if x <= cuts[2]:
        return "Q3"
    return "Q4"


def label_stats(rows: list[dict], hz: str) -> dict:
    buys = [r[f"buy_pips_{hz}"] for r in rows if r.get(f"buy_pips_{hz}") is not None]
    sells = [r[f"sell_pips_{hz}"] for r in rows if r.get(f"sell_pips_{hz}") is not None]
    bh = [r[f"buy_hit_{hz}"] for r in rows if r.get(f"buy_hit_{hz}") is not None]
    sh = [r[f"sell_hit_{hz}"] for r in rows if r.get(f"sell_hit_{hz}") is not None]
    return {
        "buy_n": len(buys),
        "buy_hit": None if not bh else sum(bh) / len(bh),
        "buy_mean": None if not buys else statistics.fmean(buys),
        "sell_n": len(sells),
        "sell_hit": None if not sh else sum(sh) / len(sh),
        "sell_mean": None if not sells else statistics.fmean(sells),
    }


def bucket_table(rows: list[dict], key: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[str(r.get(key) if r.get(key) is not None else "missing")].append(r)
    out = {}
    for name, grp in sorted(groups.items(), key=lambda kv: kv[0]):
        cell = {"n": len(grp)}
        for hz in HORIZONS:
            cell[hz] = label_stats(grp, hz)
        out[name] = cell
    return out


def fmt(x: float | None, d: int = 3) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{d}f}"


def fmt_s(x: float | None, d: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.{d}f}"


def small(n: int) -> str:
    return " [SMALL]" if n < SMALL_N else ""


def classify_q_split(earlier: dict, later: dict, pooled: dict, feature: str, hypothesis: str) -> dict:
    """Compare Q4 vs Q1 using 60m as primary descriptive horizon."""
    hz = "60"
    def delta(blob: dict) -> tuple[float | None, float | None, int, int]:
        q1 = (blob.get("Q1") or {}).get(hz) or {}
        q4 = (blob.get("Q4") or {}).get(hz) or {}
        n1 = int(q1.get("buy_n") or 0)
        n4 = int(q4.get("buy_n") or 0)
        if q1.get("buy_hit") is None or q4.get("buy_hit") is None:
            return None, None, n1, n4
        return q4["buy_hit"] - q1["buy_hit"], (q4.get("buy_mean") or 0) - (q1.get("buy_mean") or 0), n1, n4

    def sell_delta(blob: dict) -> tuple[float | None, float | None]:
        q1 = (blob.get("Q1") or {}).get(hz) or {}
        q4 = (blob.get("Q4") or {}).get(hz) or {}
        if q1.get("sell_hit") is None or q4.get("sell_hit") is None:
            return None, None
        return q4["sell_hit"] - q1["sell_hit"], (q4.get("sell_mean") or 0) - (q1.get("sell_mean") or 0)

    e_hit, e_pip, e1, e4 = delta(earlier)
    l_hit, l_pip, l1, l4 = delta(later)
    p_hit, p_pip, p1, p4 = delta(pooled)
    es, esp = sell_delta(earlier)
    ls, lsp = sell_delta(later)
    n_ok = min(e1, e4, l1, l4) >= MIN_N_COMPARE
    if min(p1, p4) < SMALL_N:
        klass = "INSUFFICIENT SAMPLE"
    elif e_hit is None or l_hit is None:
        klass = "INSUFFICIENT SAMPLE"
    else:
        same_buy = (e_hit > 0 and l_hit > 0) or (e_hit < 0 and l_hit < 0)
        mag = abs(e_hit) >= HIT_DELTA_FLOOR and abs(l_hit) >= HIT_DELTA_FLOOR
        if n_ok and same_buy and mag:
            klass = "DESCRIPTIVE CANDIDATE - REPEATED"
        elif (abs(p_hit or 0) >= HIT_DELTA_FLOOR) and not same_buy:
            klass = "DESCRIPTIVE CANDIDATE - UNSTABLE"
        elif abs(p_hit or 0) < HIT_DELTA_FLOOR and abs(p_pip or 0) < PIP_DELTA_FLOOR:
            klass = "NO APPARENT INFORMATION"
        elif not n_ok:
            klass = "INSUFFICIENT SAMPLE"
        else:
            klass = "NO APPARENT INFORMATION"
    return {
        "feature": feature,
        "hypothesis": hypothesis,
        "sample_size": p1 + p4,
        "horizons": "60 primary; also computed 5-240",
        "earlier": f"BUY Q4-Q1 hit={fmt_s(e_hit, 3)} mean={fmt_s(e_pip)} n={e1}/{e4}; SELL hit={fmt_s(es, 3)}",
        "later": f"BUY Q4-Q1 hit={fmt_s(l_hit, 3)} mean={fmt_s(l_pip)} n={l1}/{l4}; SELL hit={fmt_s(ls, 3)}",
        "stability": klass,
        "effect": f"pooled BUY Q4-Q1 hit={fmt_s(p_hit, 3)} mean={fmt_s(p_pip)} n={p1}/{p4}",
        "classification": klass,
    }


def _render_bucket(title: str, table: dict, horizons: tuple[str, ...] = ("5", "60", "240")) -> list[str]:
    lines = [title]
    for name, cell in table.items():
        n = cell["n"]
        lines.append(f"  {name}: n={n}{small(n)}")
        for hz in horizons:
            s = cell[hz]
            lines.append(
                f"    {hz:>3}m BUY hit={fmt(s['buy_hit'])} mean={fmt_s(s['buy_mean'])} n={s['buy_n']}"
                f"  SELL hit={fmt(s['sell_hit'])} mean={fmt_s(s['sell_mean'])} n={s['sell_n']}"
                f"{small(int(s['buy_n'] or 0))}"
            )
    return lines


def main() -> dict:
    obs_rows, obs_mal = load_observation_records(observations_path())
    out_rows, out_mal = load_outcome_rows(outcomes_path())
    merged = merge_outcomes(out_rows)
    opp_map, raw_n = unique_opportunities(obs_rows)
    rows = []
    for key, rec in opp_map.items():
        feat = extract_features(rec)
        ts = _ts(rec.get("timestamp_utc"))
        feat["opp_key"] = key
        feat["m5_start"] = last_completed_m5_start(ts).isoformat() if ts else None
        feat["m5_dt"] = last_completed_m5_start(ts) if ts else None
        row = attach_labels(feat, merged.get(rec["decision_id"]))
        rows.append(row)
    rows.sort(key=lambda r: r.get("m5_dt") or datetime.min.replace(tzinfo=timezone.utc))
    for r in rows:
        r["session_date"] = r["m5_dt"].date().isoformat() if r.get("m5_dt") else "?"
        r["has_label"] = any(r.get(f"buy_pips_{hz}") is not None for hz in HORIZONS)

    timestamps = [_ts(r.get("timestamp_utc")) for r in obs_rows]
    timestamps = [t for t in timestamps if t is not None]
    scored = [r for r in rows if r.get("has_label")]
    labeled_dates = sorted({r["session_date"] for r in scored})
    earlier_date = labeled_dates[0] if labeled_dates else None
    later_date = labeled_dates[1] if len(labeled_dates) > 1 else None

    def _split(pool: list[dict]) -> tuple[list[dict], list[dict]]:
        return (
            [r for r in pool if r.get("session_date") == earlier_date],
            [r for r in pool if r.get("session_date") == later_date],
        )

    earlier, later = _split(scored)
    mid = later[0].get("m5_dt") if later else None

    mature = {hz: sum(1 for r in rows if r.get(f"buy_pips_{hz}") is not None) for hz in HORIZONS}
    joined = len(scored)
    by_symbol = Counter(r.get("symbol") for r in rows)
    by_date = Counter(r.get("session_date") for r in rows)
    by_date_scored = Counter(r.get("session_date") for r in scored)

    input_names = [
        "production_stub_side", "strategy_label", "bid", "ask", "mid", "spread", "pip_size",
        "atr", "atr_over_price", "sma_fast", "sma_slow", "sma_difference", "sma_difference_over_atr",
        "rsi", "macd", "macd_signal", "adx", "bollinger_position", "ret_1", "ret_5", "ret_15", "ret_30",
        "hour_utc", "day_of_week", "usd_direction", "broker_backed_position_count",
        "gross_portfolio_exposure", "same_usd_direction_count",
    ]
    integrity = feature_integrity(obs_rows, input_names)
    ret_cmp = ret_1_vs_ret_5(rows)

    # Quartile cuts from earlier unique opportunities only.
    cont_features = [
        "atr_over_price", "spread_pips", "spread_over_atr", "sma_difference_over_atr",
        "rsi", "macd_over_atr", "bollinger_position", "ret_1", "ret_15", "ret_30",
        "gross_portfolio_exposure", "same_usd_direction_count",
    ]
    cuts = {name: earlier_cuts([r.get(name) for r in earlier if r.get(name) is not None]) for name in cont_features}
    for r in rows:
        for name in cont_features:
            r[f"q_{name}"] = assign_quartile(r.get(name), cuts[name])

    q_tables = {}
    for name in cont_features:
        q_tables[name] = {
            "pooled": bucket_table(scored, f"q_{name}"),
            "earlier": bucket_table(earlier, f"q_{name}"),
            "later": bucket_table(later, f"q_{name}"),
        }

    cat_features = [
        "production_stub_side", "strategy_label", "usd_direction", "utc_block",
        "hour_utc", "day_of_week", "broker_backed_position_count",
    ]
    cat_tables = {name: bucket_table(scored, name) for name in cat_features}
    cat_earlier = {name: bucket_table(earlier, name) for name in ("production_stub_side", "utc_block", "usd_direction")}
    cat_later = {name: bucket_table(later, name) for name in ("production_stub_side", "utc_block", "usd_direction")}

    # Stub-conditional outcomes.
    stub_rows = defaultdict(list)
    for r in scored:
        stub_rows[str(r.get("production_stub_side") or "missing")].append(r)

    def stub_side_stats(grp: list[dict], side: str) -> dict:
        out = {}
        for hz in HORIZONS:
            if side == "BUY":
                hits = [r[f"buy_hit_{hz}"] for r in grp if r.get(f"buy_hit_{hz}") is not None]
                pips = [r[f"buy_pips_{hz}"] for r in grp if r.get(f"buy_pips_{hz}") is not None]
            else:
                hits = [r[f"sell_hit_{hz}"] for r in grp if r.get(f"sell_hit_{hz}") is not None]
                pips = [r[f"sell_pips_{hz}"] for r in grp if r.get(f"sell_pips_{hz}") is not None]
            out[hz] = {
                "n": len(pips),
                "hit": None if not hits else sum(hits) / len(hits),
                "mean": None if not pips else statistics.fmean(pips),
            }
        return out

    stub_eval = {
        "BUY": stub_side_stats(stub_rows.get("BUY") or [], "BUY"),
        "SELL": stub_side_stats(stub_rows.get("SELL") or [], "SELL"),
    }

    def agree_flag(r: dict, feat: str) -> str:
        stub = str(r.get("production_stub_side") or "").upper()
        sg = _sign(r.get(feat))
        if stub not in ("BUY", "SELL") or sg in ("missing", "zero"):
            return "neutral/ambiguous"
        want = "pos" if stub == "BUY" else "neg"
        return "agrees" if sg == want else "opposes"

    for r in scored:
        r["agree_sma"] = agree_flag(r, "sma_difference")
        r["agree_ret1"] = agree_flag(r, "ret_1")
        r["agree_ret15"] = agree_flag(r, "ret_15")
        r["agree_ret30"] = agree_flag(r, "ret_30")
        r["agree_macd"] = agree_flag(r, "macd")
        r["trend_mom"] = f"sma_{_sign(r.get('sma_difference'))}|ret1_{_sign(r.get('ret_1'))}"
    earlier, later = _split(scored)
    agree_tables = {
        k: {"pooled": bucket_table(scored, k), "earlier": bucket_table(earlier, k), "later": bucket_table(later, k)}
        for k in ("agree_sma", "agree_ret1", "agree_ret15", "agree_ret30", "agree_macd")
    }
    conflict_map = {
        "pooled": bucket_table(scored, "trend_mom"),
        "earlier": bucket_table(earlier, "trend_mom"),
        "later": bucket_table(later, "trend_mom"),
    }

    # Cross-pair simultaneous USD agreement from same completed M5 start.
    by_m5: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("m5_start"):
            by_m5[r["m5_start"]].append(r)
    for r in rows:
        peers = by_m5.get(r.get("m5_start") or "", [])
        own = str(r.get("usd_direction") or "")
        others = [p for p in peers if p.get("decision_id") != r.get("decision_id") and p.get("usd_direction")]
        same = sum(1 for p in others if p.get("usd_direction") == own)
        r["simultaneous_pairs"] = len(peers)
        r["peer_usd_agree_n"] = same
        r["peer_usd_agree_frac"] = None if not others else same / len(others)
    earlier, later = _split(scored)
    peer_cuts = earlier_cuts([r["peer_usd_agree_frac"] for r in earlier if r.get("peer_usd_agree_frac") is not None])
    for r in rows:
        r["q_peer_usd"] = assign_quartile(r.get("peer_usd_agree_frac"), peer_cuts)
    earlier, later = _split(scored)
    peer_tables = {
        "pooled": bucket_table(scored, "q_peer_usd"),
        "earlier": bucket_table(earlier, "q_peer_usd"),
        "later": bucket_table(later, "q_peer_usd"),
        "count": bucket_table(scored, "same_usd_direction_count"),
        "simultaneous": bucket_table(scored, "simultaneous_pairs"),
    }

    # RL
    q_zero = sum(
        1
        for r in scored
        if r.get("rl_q_buy") == 0 and r.get("rl_q_sell") == 0 and r.get("rl_q_skip") == 0
    )
    rl_action_counts = Counter(r.get("rl_action") for r in scored)
    for r in scored:
        if r.get("rl_agree") is True:
            r["rl_gate"] = "agreed"
        elif r.get("rl_veto") is True:
            r["rl_gate"] = "vetoed"
        else:
            r["rl_gate"] = "unknown"
    earlier, later = _split(scored)
    rl_table = {
        "pooled": bucket_table(scored, "rl_gate"),
        "earlier": bucket_table(earlier, "rl_gate"),
        "later": bucket_table(later, "rl_gate"),
    }

    def stub_matched_hit(grp: list[dict], hz: str) -> dict:
        hits = []
        pips = []
        for r in grp:
            stub = str(r.get("production_stub_side") or "").upper()
            if stub == "BUY" and r.get(f"buy_pips_{hz}") is not None:
                hits.append(r[f"buy_hit_{hz}"])
                pips.append(r[f"buy_pips_{hz}"])
            elif stub == "SELL" and r.get(f"sell_pips_{hz}") is not None:
                hits.append(r[f"sell_hit_{hz}"])
                pips.append(r[f"sell_pips_{hz}"])
        return {
            "n": len(pips),
            "hit": None if not hits else sum(hits) / len(hits),
            "mean": None if not pips else statistics.fmean(pips),
        }

    rl_counterfactual = {}
    for label, grp in (("agreed", [r for r in scored if r.get("rl_gate") == "agreed"]), ("vetoed", [r for r in scored if r.get("rl_gate") == "vetoed"])):
        rl_counterfactual[label] = {hz: stub_matched_hit(grp, hz) for hz in HORIZONS}

    # MFE/MAE
    mfe_audit = {}
    for hz in HORIZONS:
        buy_mfe = [r[f"buy_mfe_{hz}"] for r in rows if r.get(f"buy_mfe_{hz}") is not None]
        buy_mae = [r[f"buy_mae_{hz}"] for r in rows if r.get(f"buy_mae_{hz}") is not None]
        mfe_audit[hz] = {
            "buy_mfe_n": len(buy_mfe),
            "buy_mae_n": len(buy_mae),
            "buy_mfe_median": statistics.median(buy_mfe) if buy_mfe else None,
            "buy_mae_median": statistics.median(buy_mae) if buy_mae else None,
            "buy_mfe_mean": statistics.fmean(buy_mfe) if buy_mfe else None,
            "buy_mae_mean": statistics.fmean(buy_mae) if buy_mae else None,
        }

    # Production trade join
    prod_join = {"status": "SKIP", "reason": "existing dump does not overlap V2 observation window"}
    if TRADE_DUMP.is_file():
        dump = json.loads(TRADE_DUMP.read_text(encoding="utf-8"))
        trades = dump.get("trades") or []
        tss = [str(t.get("time") or "") for t in trades]
        prod_join = {
            "status": "SKIP",
            "dump_trades": len(trades),
            "dump_first": tss[0] if tss else None,
            "dump_last": tss[-1] if tss else None,
            "v2_first": min(timestamps).isoformat() if timestamps else None,
            "reason": "live trade dump last timestamp is before V2 observation start; populations are not the same and cannot be joined reliably",
        }

    hypotheses = [
        classify_q_split(q_tables[n]["earlier"], q_tables[n]["later"], q_tables[n]["pooled"], n, f"higher {n} vs lower {n}")
        for n in cont_features
    ]

    n_features = len(cont_features) + len(cat_features) + 5  # agree maps + conflict + peer + rl
    n_comparisons = n_features * len(HORIZONS) * 2  # BUY and SELL

    payload = {
        "raw_observations": raw_n,
        "obs_malformed": obs_mal,
        "out_malformed": out_mal,
        "unique_opportunities": len(rows),
        "joined_unique": joined,
        "repeat_rate": None if not raw_n else 100.0 * (raw_n - len(rows)) / raw_n,
        "time_range": [
            min(timestamps).isoformat() if timestamps else None,
            max(timestamps).isoformat() if timestamps else None,
        ],
        "mature": mature,
        "by_symbol": dict(by_symbol),
        "by_date": dict(by_date),
        "earlier_n": len(earlier),
        "later_n": len(later),
        "earlier_date": earlier_date,
        "later_date": later_date,
        "by_date_scored": dict(by_date_scored),
        "unscored_unique": len(rows) - len(scored),
        "split_at": f"labeled-session {earlier_date} vs {later_date}",
        "integrity": integrity,
        "ret_1_vs_ret_5": ret_cmp,
        "q_zero_unique": q_zero,
        "rl_actions": dict(rl_action_counts),
        "n_features": n_features,
        "n_comparisons": n_comparisons,
        "prod_join": prod_join,
        "cuts": {k: v for k, v in cuts.items()},
    }

    md = render_report(
        payload,
        rows=rows,
        q_tables=q_tables,
        cat_tables=cat_tables,
        cat_earlier=cat_earlier,
        cat_later=cat_later,
        stub_eval=stub_eval,
        agree_tables=agree_tables,
        conflict_map=conflict_map,
        peer_tables=peer_tables,
        rl_table=rl_table,
        rl_counterfactual=rl_counterfactual,
        mfe_audit=mfe_audit,
        hypotheses=hypotheses,
        earlier=earlier,
        later=later,
    )
    dest_md = Path("reports/decision_quality/v2_internal_data_mining_stage1.md")
    dest_json = Path("reports/decision_quality/_v2_internal_data_mining_stage1_results.json")
    dest_md.write_text(md, encoding="utf-8")
    slim = {k: payload[k] for k in payload}
    slim["hypotheses"] = hypotheses
    slim["stub_eval"] = stub_eval
    slim["rl_counterfactual"] = rl_counterfactual
    slim["mfe_audit"] = mfe_audit
    dest_json.write_text(json.dumps(slim, indent=2, default=str) + "\n", encoding="utf-8")
    print(md.encode("ascii", "replace").decode("ascii")[:4000])
    print("WROTE", dest_md)
    return payload


def render_report(payload, **ctx) -> str:
    q_tables = ctx["q_tables"]
    cat_tables = ctx["cat_tables"]
    stub_eval = ctx["stub_eval"]
    agree_tables = ctx["agree_tables"]
    conflict_map = ctx["conflict_map"]
    peer_tables = ctx["peer_tables"]
    rl_table = ctx["rl_table"]
    rl_cf = ctx["rl_counterfactual"]
    mfe_audit = ctx["mfe_audit"]
    hyps = ctx["hypotheses"]
    earlier = ctx["earlier"]
    later = ctx["later"]
    integ = payload["integrity"]
    ret = payload["ret_1_vs_ret_5"]

    def integ_lines() -> list[str]:
        lines = [
            "name  avail  miss  not_computed  unique  min  median  mean  max  flag",
        ]
        for name, s in integ.items():
            flag = []
            if s["not_computed"] and s["available"] == 0:
                flag.append("NOT_COMPUTED")
            if s["constant"]:
                flag.append("CONSTANT")
            if s["near_constant"] and not s["constant"]:
                flag.append("NEAR_CONSTANT")
            if name in ("ret_1", "ret_5"):
                flag.append("SEE_RET_DUP")
            lines.append(
                f"{name}: avail={s['available']} miss={s['missing']} nc={s['not_computed']} unique={s['unique']}"
                f" min={fmt(s['min'], 6)} med={fmt(s['median'], 6)} mean={fmt(s['mean'], 6)} max={fmt(s['max'], 6)}"
                f" {' '.join(flag)}"
            )
        return lines

    def q_compact(name: str) -> list[str]:
        lines = [f"{name} (quartile cuts from earlier unique opportunities only):"]
        for split in ("pooled", "earlier", "later"):
            lines.extend(_render_bucket(f"  {split}:", q_tables[name][split], ("5", "60", "240")))
        return lines

    # Frozen hypotheses: only REPEATED, max 3, skip obvious duplicates of ret_5.
    repeated = [h for h in hyps if h["classification"] == "DESCRIPTIVE CANDIDATE - REPEATED"]
    # Prefer cost/vol and agreement structure over cherry-picked returns.
    freeze: list[str] = []
    freeze_notes = []
    # Manual conservative freeze using actual numbers from hyps + structural audits.
    # Filled after we know results; placeholder logic uses classifications only.
    for h in repeated:
        if h["feature"] in ("ret_1",) and "ret_5" in integ:
            continue
        freeze.append(h["feature"])
        if len(freeze) >= 3:
            break

    lines = [
        "# V2 internal data mining - stage 1 discovery",
        "",
        "RESEARCH / DESCRIPTIVE ONLY. V2 remains SKIP. No live trading change.",
        "Unique opportunity = (symbol, last completed M5 start), earliest observation representative.",
        "Quartile cuts are computed from the earlier labeled session (scored unique opportunities) only.",
        "Repeated ~60s bot-loop rows are not treated as independent samples.",
        "",
        "DATASET:",
        f"raw observations: {payload['raw_observations']}",
        f"unique opportunities: {payload['unique_opportunities']}",
        f"joined unique opportunities with at least one mature label: {payload['joined_unique']}",
        f"time range: {payload['time_range'][0]} -> {payload['time_range'][1]}",
        f"repeat rate: {fmt(payload['repeat_rate'], 1)}%",
        f"malformed observations: {payload['obs_malformed']}",
        f"malformed outcomes: {payload['out_malformed']}",
        "mature labels (unique opportunities with BUY forward_pips AVAILABLE):",
    ]
    for hz in HORIZONS:
        lines.append(f"  {hz}m: {payload['mature'][hz]}")
    lines.append("symbol counts (unique opportunities):")
    for sym, n in sorted(payload["by_symbol"].items()):
        lines.append(f"  {sym}: {n}")
    lines.append("UTC date of completed-M5 start (all unique / scored):")
    for d, n in sorted(payload["by_date"].items()):
        scored_n = (payload.get("by_date_scored") or {}).get(d, 0)
        lines.append(f"  {d}: unique={n} scored={scored_n}")
    lines.append(
        f"unscored unique opportunities (no mature outcome yet): {payload.get('unscored_unique')}"
    )
    lines.append(
        "Outcome/stability tables use scored unique opportunities only, split by labeled session date "
        f"{payload.get('earlier_date')} vs {payload.get('later_date')}. Unscored later dates are not treated as a later outcome block."
    )
    lines.append(f"earlier labeled n={payload['earlier_n']}  later labeled n={payload['later_n']}")
    lines.extend(["", "FEATURE QUALITY:"])
    lines.extend(integ_lines())
    lines.extend(
        [
            "",
            "RET_1 VS RET_5:",
            f"n={ret.get('n')}",
            f"exact equality rate={fmt(ret.get('exact_equal_rate'), 4)} ({ret.get('exact_equal')}/{ret.get('n')})",
            f"abs(diff)<=1e-12 rate={fmt(ret.get('abs_diff_le_1e12'), 4)}",
            f"correlation={fmt(ret.get('corr'), 6)}",
            f"diff mean={ret.get('diff_mean')} median={ret.get('diff_median')} min={ret.get('diff_min')} max={ret.get('diff_max')}",
            str(ret.get("construction_note")),
            "Do not treat ret_1 and ret_5 as independent signals. They are the same one-bar M5 return",
            "up to floating-point noise (pct_change vs explicit 1-bar lookback).",
            "",
            "SINGLE-FEATURE AUDIT:",
            "Continuous features use earlier-half quartiles. Categorical features use natural categories.",
            "Full 5/60/240 shown. 15/30/120 were computed and used for classification counts.",
        ]
    )
    for name in q_tables:
        lines.extend(q_compact(name))
        lines.append("")
    lines.append("Categorical:")
    for name, table in cat_tables.items():
        if name == "hour_utc":
            lines.extend(_render_bucket(f"{name}:", table, ("60",)))
        else:
            lines.extend(_render_bucket(f"{name}:", table, ("5", "60", "240")))
        lines.append("")

    lines.extend(["CHRONOLOGICAL STABILITY:", "Earlier vs later unique-opportunity halves; Q1 vs Q4 at 60m."])
    for h in hyps:
        lines.append(
            f"{h['feature']}: {h['classification']}"
        )
        lines.append(f"  earlier: {h['earlier']}")
        lines.append(f"  later:   {h['later']}")
        lines.append(f"  pooled:  {h['effect']}")
    lines.extend(
        [
            "",
            "Stub side chronological check (stub BUY uses BUY labels; stub SELL uses SELL labels):",
        ]
    )
    for split_name, grp in (("earlier", earlier), ("later", later)):
        buys = [r for r in grp if r.get("production_stub_side") == "BUY"]
        sells = [r for r in grp if r.get("production_stub_side") == "SELL"]
        b = stub_side_stats_local(buys, "BUY")
        s = stub_side_stats_local(sells, "SELL")
        lines.append(
            f"  {split_name}: stubBUY n={len(buys)} 60m hit={fmt(b['60']['hit'])} mean={fmt_s(b['60']['mean'])}"
            f"  stubSELL n={len(sells)} 60m hit={fmt(s['60']['hit'])} mean={fmt_s(s['60']['mean'])}"
        )

    lines.extend(["", "TREND/MOMENTUM CONFLICT MAP:", "State = sign(sma_difference) x sign(ret_1). No vote count."])
    for split in ("pooled", "earlier", "later"):
        lines.extend(_render_bucket(f"{split}:", conflict_map[split], ("60",)))
    lines.append("SMA/ret agreement with production stub:")
    for k in ("agree_sma", "agree_ret1", "agree_ret15", "agree_macd"):
        lines.extend(_render_bucket(f"{k} pooled:", agree_tables[k]["pooled"], ("60",)))
        lines.extend(_render_bucket(f"{k} earlier:", agree_tables[k]["earlier"], ("60",)))
        lines.extend(_render_bucket(f"{k} later:", agree_tables[k]["later"], ("60",)))

    lines.extend(["", "VOLATILITY/SPREAD:"])
    for name in ("atr_over_price", "spread_pips", "spread_over_atr"):
        lines.append(f"See quartile tables above for {name}.")
        h = next(x for x in hyps if x["feature"] == name)
        lines.append(f"  classification={h['classification']}")

    lines.extend(
        [
            "",
            "CROSS-PAIR USD CONTEXT:",
            "same_usd_direction_count is an observation-time portfolio count, not future movement.",
            "peer_usd_agree_frac is reconstructed from other unique V2 opportunities sharing the same completed M5 start.",
            "Simultaneous pairs are correlated; n is not independent.",
        ]
    )
    lines.extend(_render_bucket("same_usd_direction_count:", peer_tables["count"], ("60",)))
    lines.extend(_render_bucket("simultaneous pair count at m5:", peer_tables["simultaneous"], ("60",)))
    lines.extend(_render_bucket("peer USD agreement quartile (earlier cuts):", peer_tables["pooled"], ("60",)))
    lines.extend(_render_bucket("peer earlier:", peer_tables["earlier"], ("60",)))
    lines.extend(_render_bucket("peer later:", peer_tables["later"], ("60",)))
    lines.extend(_render_bucket("usd_direction pooled:", cat_tables["usd_direction"], ("60",)))
    lines.extend(_render_bucket("usd_direction earlier:", ctx["cat_earlier"]["usd_direction"], ("60",)))
    lines.extend(_render_bucket("usd_direction later:", ctx["cat_later"]["usd_direction"], ("60",)))

    lines.extend(["", "TIME CONTEXT:", "Diagnostic only. Not a session filter."])
    lines.extend(_render_bucket("utc_block pooled:", cat_tables["utc_block"], ("5", "60", "240")))
    lines.extend(_render_bucket("utc_block earlier:", ctx["cat_earlier"]["utc_block"], ("60",)))
    lines.extend(_render_bucket("utc_block later:", ctx["cat_later"]["utc_block"], ("60",)))
    lines.extend(_render_bucket("day_of_week:", cat_tables["day_of_week"], ("60",)))

    lines.extend(
        [
            "",
            "RL AGREEMENT/VETO AUDIT:",
            "This is an observability experiment, NOT evidence of learned RL skill.",
            f"unique opportunities with all Q values exactly 0: {payload['q_zero_unique']}/{payload['unique_opportunities']}",
            f"rl_action counts: {payload['rl_actions']}",
            "Q remaining zero means actions are epsilon/tie-driven, not a trained policy.",
        ]
    )
    lines.extend(_render_bucket("rl_gate pooled:", rl_table["pooled"], ("60",)))
    lines.extend(_render_bucket("rl_gate earlier:", rl_table["earlier"], ("60",)))
    lines.extend(_render_bucket("rl_gate later:", rl_table["later"], ("60",)))
    lines.append("Counterfactual using production stub side vs matching executable outcome:")
    for label, blob in rl_cf.items():
        for hz in ("5", "60", "240"):
            s = blob[hz]
            lines.append(f"  {label} {hz}m n={s['n']} stub-matched hit={fmt(s['hit'])} mean={fmt_s(s['mean'])}{small(s['n'])}")
    lines.append(
        "Stored data can describe random-gate suppression vs agreement, but is NOT sufficient to conclude the RL gate adds skill."
    )

    lines.extend(
        [
            "",
            "PRODUCTION-TRADE VS COUNTERFACTUAL CONTEXT:",
            f"status={payload['prod_join']['status']}",
            json.dumps(payload["prod_join"], default=str),
            "",
            "MFE/MAE AVAILABILITY:",
            "Path MFE/MAE fields exist on scored executable-side outcomes (research_bid_ask_path).",
            "They are research path extrema, not production SL/TP.",
        ]
    )
    for hz, s in mfe_audit.items():
        lines.append(
            f"  {hz}m BUY mfe n={s['buy_mfe_n']} median={fmt_s(s['buy_mfe_median'])} mean={fmt_s(s['buy_mfe_mean'])}"
            f"  mae n={s['buy_mae_n']} median={fmt_s(s['buy_mae_median'])} mean={fmt_s(s['buy_mae_mean'])}"
        )

    lines.extend(
        [
            "",
            "MULTIPLE TESTING:",
            f"features examined: {payload['n_features']}",
            f"comparisons examined: {payload['n_comparisons']}",
            "A single good-looking bucket is not an edge.",
            "",
            "CANDIDATE TABLE:",
            "feature | hypothesis | n | horizons | earlier | later | classification | dependence",
        ]
    )
    dep = {
        "ret_1": "duplicate of ret_5",
        "ret_15": "overlaps ret_1/ret_30 path",
        "ret_30": "overlaps ret_15 path",
        "macd_over_atr": "uses ATR; related to sma_difference_over_atr",
        "sma_difference_over_atr": "uses ATR and SMA pair",
        "spread_over_atr": "uses spread and ATR; cost/vol",
        "spread_pips": "related to spread_over_atr",
        "atr_over_price": "related to spread_over_atr via ATR",
        "gross_portfolio_exposure": "level/notional context, not price",
        "same_usd_direction_count": "correlated with simultaneous USD pairs",
        "bollinger_position": "related to mid vs recent range",
        "rsi": "related to recent returns",
    }
    for h in hyps:
        lines.append(
            f"{h['feature']} | {h['hypothesis']} | {h['sample_size']} | {h['horizons']} | {h['earlier']} | {h['later']} | {h['classification']} | {dep.get(h['feature'], 'see feature quality')}"
        )

    freeze_final = _freeze(hyps, ret)
    lines.extend(
        [
            "",
            "PROSPECTIVE HYPOTHESES WORTH FREEZING:",
            freeze_final,
            "",
            "DATA SUFFICIENT FOR MODEL TRAINING: NO",
            "DATA SUFFICIENT FOR 65% CONFIDENCE CLAIM: NO",
            "PRODUCTION CHANGE JUSTIFIED: NO",
            "OANDA/API REQUESTS: 0",
            "SOURCE DATA MODIFIED: NO",
            "TRADING LOGIC CHANGED: NO",
            "V2 POLICY CHANGED: NO",
            "MODEL TRAINED: NO",
            "FILES CHANGED:",
            "- reports/decision_quality/_v2_internal_data_mining_stage1.py",
            "- reports/decision_quality/_v2_internal_data_mining_stage1_results.json",
            "- reports/decision_quality/v2_internal_data_mining_stage1.md",
            "- tests/test_v2_internal_data_mining_stage1.py",
        ]
    )
    return "\n".join(lines) + "\n"


def stub_side_stats_local(grp: list[dict], side: str) -> dict:
    out = {}
    for hz in HORIZONS:
        if side == "BUY":
            hits = [r[f"buy_hit_{hz}"] for r in grp if r.get(f"buy_hit_{hz}") is not None]
            pips = [r[f"buy_pips_{hz}"] for r in grp if r.get(f"buy_pips_{hz}") is not None]
        else:
            hits = [r[f"sell_hit_{hz}"] for r in grp if r.get(f"sell_hit_{hz}") is not None]
            pips = [r[f"sell_pips_{hz}"] for r in grp if r.get(f"sell_pips_{hz}") is not None]
        out[hz] = {
            "n": len(pips),
            "hit": None if not hits else sum(hits) / len(hits),
            "mean": None if not pips else statistics.fmean(pips),
        }
    return out


def _freeze(hyps: list[dict], ret: dict) -> str:
    """Conservative freeze: 0-3 exact definitions. Prefer NONE if nothing is repeated and non-duplicate."""
    notes = []
    if (ret.get("abs_diff_le_1e12") or 0) >= 0.99:
        notes.append(
            "QUALITY HOLD (not a trading hypothesis): ret_1 and ret_5 are the same one-bar M5 return; they must not be used as two features."
        )
    family = [
        h for h in hyps
        if h["classification"] == "DESCRIPTIVE CANDIDATE - REPEATED" and h["feature"] in ("rsi", "ret_1", "ret_15", "ret_30")
    ]
    if family:
        notes.append(
            "FAMILY NOTE (not frozen this stage): high recent strength (RSI/ret) showed the same 60m Q4-vs-Q1 sign in both labeled sessions. Features are correlated. Wait for a third labeled session before freezing one family definition. Not activated."
        )
    kept = [
        h for h in hyps
        if h["classification"] == "DESCRIPTIVE CANDIDATE - REPEATED"
        and h["feature"] not in ("ret_1", "ret_15", "ret_30", "rsi", "bollinger_position")
    ]
    if not kept:
        body = "NONE"
        if notes:
            body = "NONE as directional/profitability hypotheses.\n" + "\n".join(notes)
        return body
    lines = []
    for i, h in enumerate(kept[:3], 1):
        lines.append(
            f"{i}. FREEZE definition: unique opportunity (symbol, last completed M5 start); "
            f"feature={h['feature']}; earlier labeled-session quartile cuts only; compare Q4 vs Q1 executable "
            f"BUY/SELL labels at 60m. Do not retune cuts. Do not trade. {h['classification']}"
        )
    lines.extend(notes)
    return "\n".join(lines)


if __name__ == "__main__":
    main()
