"""Validated candles, causal numerical adapters and account-currency arithmetic."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import math
from pathlib import Path
import statistics

PAIRS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
STRATEGIES = ("scalp", "trend", "mean_reversion", "swing_trend",
              "swing_mean_reversion", "swing_breakout")


class ResearchRejected(ValueError):
    pass


def pip_size(pair):
    if pair not in PAIRS:
        raise ResearchRejected("unsupported_instrument")
    return .01 if pair.endswith("_JPY") else .0001


def timestamp(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ResearchRejected("naive_timestamp")
    if dt.microsecond:
        raise ResearchRejected("fractional_bar_timestamp")
    return int(dt.astimezone(timezone.utc).timestamp())


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def utc(t):
    return datetime.fromtimestamp(t, timezone.utc)


@dataclass(frozen=True, slots=True)
class Bar:
    t: int  # UTC start; completion/availability is t+300
    o: float
    h: float
    l: float
    c: float
    bo: float
    bh: float
    bl: float
    bc: float
    ao: float
    ah: float
    al: float
    ac: float
    complete: bool = True


def validate(bars):
    errors = []
    gaps = []
    previous = None
    for i, b in enumerate(bars):
        if not b.complete:
            errors.append((i, "incomplete"))
        if type(b.t) is not int or b.t % 300:
            errors.append((i, "off_grid"))
        if previous is not None:
            if b.t <= previous:
                errors.append((i, "duplicate" if b.t == previous else "unordered"))
            elif b.t - previous > 300:
                weekend = utc(previous).weekday() >= 4 and utc(b.t).weekday() in (6, 0)
                gaps.append({"before": iso(previous), "after": iso(b.t),
                             "missing_bars": (b.t - previous) // 300 - 1,
                             "kind": "weekend_containing" if weekend else "unexpected"})
        previous = b.t
        for o, h, l, c in ((b.o, b.h, b.l, b.c), (b.bo, b.bh, b.bl, b.bc),
                           (b.ao, b.ah, b.al, b.ac)):
            if (not all(math.isfinite(x) and x > 0 for x in (o, h, l, c))
                    or l > min(o, c) or h < max(o, c) or l > h):
                errors.append((i, "ohlc_invalid"))
                break
        if any(bid > ask for bid, ask in ((b.bo, b.ao), (b.bc, b.ac), (b.bh, b.ah), (b.bl, b.al))):
            errors.append((i, "crossed_quote"))
    return {"rows": len(bars), "start": iso(bars[0].t) if bars else None,
            "end": iso(bars[-1].t) if bars else None, "errors": errors,
            "gaps": gaps, "status": "FAIL" if errors or not bars else ("WARN" if gaps else "PASS")}


def read_csv(path):
    """No sorting, interpolation, mid-to-bid fabrication, or invalid-row repair."""
    bars, excluded = [], []
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        g3 = "bid_o" in (reader.fieldnames or [])
        for index, row in enumerate(reader):
            if str(row.get("complete", "")).lower() not in ("true", "1"):
                excluded.append({"row": index, "reason": "not_explicitly_complete"})
                continue
            try:
                names = ("mid_o", "mid_h", "mid_l", "mid_c", "bid_o", "bid_h", "bid_l", "bid_c",
                         "ask_o", "ask_h", "ask_l", "ask_c") if g3 else (
                         "open", "high", "low", "close", "bid_open", "bid_high", "bid_low", "bid_close",
                         "ask_open", "ask_high", "ask_low", "ask_close")
                bars.append(Bar(timestamp(row["time"]), *(float(row[k]) for k in names)))
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ResearchRejected(f"invalid_csv_row:{index}:{type(exc).__name__}") from exc
    quality = validate(bars)
    quality.update(excluded=excluded, sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                   bid_ask="observed", timestamp="UTC", pip_precision="source values preserved")
    if quality["status"] == "FAIL":
        raise ResearchRejected("dataset_validation_failed:" + str(quality["errors"][:3]))
    return bars, quality


def features(bars, lookback):
    """Stdlib adapter of compute_indicators' warmed-up MA/ATR/BB formulas.

    Only periods used by the existing shadow rule are computed. Unchanged
    operational latest_atr_price is a simple rolling true-range mean of 14.
    Reset warm-up after a gap; no future rows, full-sample fits, or bfill.
    """
    n = len(bars)
    pack = {k: [math.nan] * n for k in ("close", "high", "low", "ma_fast", "ma_slow",
                                       "atr", "atr14", "boll_up", "boll_down", "prior_hi", "prior_lo")}
    pack.update(n=n, regime=["WARMUP"] * n, volatility=["UNKNOWN"] * n,
                momentum=["UNKNOWN"] * n, atr_median=[math.nan] * n)
    closes, ranges, history = deque(maxlen=lookback), deque(maxlen=lookback), deque(maxlen=lookback)
    prior_atrs = deque(maxlen=250)
    fast, slow, atr_n = max(3, lookback // 10), max(4, lookback // 2), max(7, min(30, lookback // 5))
    previous = None
    for i, b in enumerate(bars):
        if previous is not None and b.t - previous.t != 300:
            closes.clear(); ranges.clear(); history.clear(); prior_atrs.clear()
        tr = b.h - b.l if not history else max(b.h - b.l, abs(b.h - history[-1].c), abs(b.l - history[-1].c))
        highs = [r.h for r in list(history)[-20:]]
        lows = [r.l for r in list(history)[-20:]]
        closes.append(b.c); ranges.append(tr); history.append(b)
        pack["close"][i], pack["high"][i], pack["low"][i] = b.c, b.h, b.l
        # Full fixed warm-up avoids the operational early length-dependent periods.
        if len(history) >= lookback:
            c, r = list(closes), list(ranges)
            mf, ms, atr = statistics.fmean(c[-fast:]), statistics.fmean(c[-slow:]), statistics.fmean(r[-atr_n:])
            sd = statistics.stdev(c[-slow:])
            for key, value in (("ma_fast", mf), ("ma_slow", ms), ("atr", atr),
                               ("atr14", statistics.fmean(r[-14:])), ("boll_up", ms + 2 * sd),
                               ("boll_down", ms - 2 * sd), ("prior_hi", max(highs)), ("prior_lo", min(lows))):
                pack[key][i] = value
            strength = abs(mf - ms) / atr if atr > 0 else 0
            pack["regime"][i] = "TREND" if strength >= .5 else ("RANGE" if strength <= .15 else "UNCERTAIN")
            ref = statistics.median(prior_atrs) if prior_atrs else atr
            pack["atr_median"][i] = ref
            pack["volatility"][i] = "HIGH" if atr > ref * 1.5 else ("LOW" if atr < ref * .67 else "NORMAL")
            pack["momentum"][i] = "STRONG" if atr > 0 and abs(c[-1] - c[-6]) / atr >= 1 else "WEAK"
            prior_atrs.append(atr)
        previous = b
    return pack


@dataclass(frozen=True)
class Config:
    account: str = "USD"
    initial: float = 10000.0
    risk_fraction: float = .0025
    portfolio_risk: float = .02
    max_positions: int = 6
    usd_slots: int = 2
    leverage: float = 20.0
    margin_fraction: float = .8
    stop_atr: float = 2.0
    reward_risk: float = 2.0
    min_stop_pips: float = 4.0
    slippage_pips: float = .2
    commission_per_100k_side: float = 3.0  # account units, assumption not broker fee
    max_hold_bars: int = 12
    flatten_hour_utc: int = 20
    flatten_minute: int = 55

    def __post_init__(self):
        if self.account not in {"USD", "GBP", "EUR", "JPY", "AUD", "CAD", "CHF"}:
            raise ResearchRejected("unsupported_account_currency")
        for name in ("initial", "risk_fraction", "portfolio_risk", "leverage", "margin_fraction",
                     "stop_atr", "reward_risk", "min_stop_pips", "slippage_pips", "commission_per_100k_side"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ResearchRejected("invalid_config:" + name)
        if not (self.initial > 0 and 0 < self.risk_fraction <= self.portfolio_risk <= 1
                and self.leverage > 0 and 0 < self.margin_fraction <= 1 and self.stop_atr > 0
                and self.reward_risk > 0 and self.min_stop_pips > 0):
            raise ResearchRejected("invalid_risk_config")
        if any(type(getattr(self, k)) is not int or getattr(self, k) < 1
               for k in ("max_positions", "usd_slots", "max_hold_bars")):
            raise ResearchRejected("invalid_integer_config")
        if (type(self.flatten_hour_utc) is not int or not 0 <= self.flatten_hour_utc < 24
                or type(self.flatten_minute) is not int or not 0 <= self.flatten_minute < 60):
            raise ResearchRejected("invalid_session_config")


class Quotes:
    def __init__(self):
        self.book = {}

    def put(self, pair, t, bid, ask):
        if not (0 < bid <= ask and all(math.isfinite(x) for x in (bid, ask))):
            raise ResearchRejected("invalid_conversion_quote")
        self.book[pair] = (t, bid, ask)

    def convert(self, amount, source, target, when, *, override=None):
        if not math.isfinite(amount):
            raise ResearchRejected("nonfinite_money")
        if source == target:
            return amount
        edges = {}
        book = dict(self.book)
        if override:
            book.update(override)
        for pair, (asof, bid, ask) in sorted(book.items()):
            if not 0 <= when - asof <= 300:
                continue
            base, quote = pair.split("_")
            edges.setdefault(base, []).append((quote, bid if amount >= 0 else ask))
            edges.setdefault(quote, []).append((base, 1 / (ask if amount >= 0 else bid)))
        queue = [(source, amount, {source})]
        for ccy, value, seen in queue:
            for nxt, rate in edges.get(ccy, []):
                if nxt in seen:
                    continue
                if nxt == target:
                    return value * rate
                queue.append((nxt, value * rate, seen | {nxt}))
        raise ResearchRejected("conversion_unavailable_or_stale:" + source + ":" + target)


def usd_direction(pair, side):
    base, quote = pair.split("_")
    if base == "USD":
        return "LONG" if side == "BUY" else "SHORT"
    if quote == "USD":
        return "SHORT" if side == "BUY" else "LONG"
    return None


def periods(times):
    """Expanding train/validation windows; nonoverlapping tests, final 20% locked."""
    if len(times) < 1000:
        raise ResearchRejected("insufficient_walk_forward_data")
    n = len(times)
    return [dict(fold=1, train=(times[0], times[int(n * .5)]),
                 validation=(times[int(n * .5)], times[int(n * .65)]),
                 test=(times[int(n * .65)], times[int(n * .8)])),
            dict(fold=2, train=(times[0], times[int(n * .65)]),
                 validation=(times[int(n * .65)], times[int(n * .8)]),
                 test=(times[int(n * .8)], times[-1] + 300))]
