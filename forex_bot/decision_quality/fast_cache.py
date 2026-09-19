"""Causal precompute for the offline engine. Research-only; does not change live trading."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.decision_quality.invariants import sl_tp_from_production_distances
from forex_bot.decision_quality.research_features import (
    _trend_label,
    atr_percentile,
    classify_regime,
    distance_from_swing_atr,
    htf_alignment,
    pre_entry_extension_atr,
    wilder_adx,
)
from forex_bot.decision_quality.sessions import classify_session, hour_london, hour_utc
from forex_bot.decision_quality.signal import _env_int, seeded_select_strategy
from forex_bot.decision_quality.snapshot import DecisionSnapshot
from forex_bot.indicators import _true_range, compute_indicators
from forex_bot.profit_protection import pip_size
from forex_bot.session_rules import fx_market_open_at, in_active_session_at, volatility_ok
from forex_bot.trading import simulated_half_spread


def _period_tuple(lookback: int, n: int) -> tuple[int, int, int, int]:
    """Match ``compute_indicators`` period lengths for a frame of length ``n``."""
    if n <= 0:
        return (0, 0, 0, 0)
    lb = max(20, min(int(lookback), max(n, 20)))
    cap = n - 1
    ma_fast_n = max(3, min(lb // 10, cap))
    ma_slow_n = max(ma_fast_n + 1, min(lb // 2, cap))
    atr_n = max(7, min(lb // 5, min(30, cap)))
    rsi_n = max(7, min(14, lb // 4))
    return ma_fast_n, ma_slow_n, atr_n, rsi_n


def _adx_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = _true_range(high, low, close)
    alpha = 1.0 / period
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100.0 * (plus_dm.ewm(alpha=alpha, adjust=False).mean() / (atr + 1e-12))
    minus_di = 100.0 * (minus_dm.ewm(alpha=alpha, adjust=False).mean() / (atr + 1e-12))
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-12)
    return dx.ewm(alpha=alpha, adjust=False).mean()


class SignalCache:
    """Full-series causal caches. Row i is legal at bar i (no future bars)."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.n = len(df)
        self._ind: dict[int, pd.DataFrame] = {}
        self._adx = _adx_series(df) if self.n else pd.Series(dtype=float)
        self._htf: dict[str, pd.DataFrame] = {}
        if self.n:
            self._htf = {
                "M15": self._resample("15min"),
                "H1": self._resample("1h"),
                "H4": self._resample("4h"),
            }

    def _resample(self, rule: str) -> pd.DataFrame:
        idx = self.df.set_index(pd.to_datetime(self.df["time"]))
        ohlc = idx.resample(rule, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}
        )
        ohlc = ohlc.dropna(how="any")
        if ohlc.empty:
            out = ohlc.reset_index().rename(columns={"index": "time"})
            out["end"] = pd.NaT
            return out
        delta = pd.tseries.frequencies.to_offset(rule)
        out = ohlc.reset_index()
        out = out.rename(columns={out.columns[0]: "time"})
        out["end"] = pd.to_datetime(out["time"]) + delta
        return out

    def indicators(self, lookback: int) -> pd.DataFrame:
        lb = int(lookback)
        if lb not in self._ind:
            self._ind[lb] = compute_indicators(self.df, lookback=lb)
        return self._ind[lb]

    def prefix_indicators(self, lookback: int, i: int) -> pd.DataFrame:
        """Indicator frame covering bars ``0..i`` with prefix-correct periods."""
        n_pref = i + 1
        cached = self.indicators(lookback)
        if _period_tuple(lookback, n_pref) == _period_tuple(lookback, self.n):
            return cached.iloc[:n_pref]
        return compute_indicators(self.df.iloc[:n_pref], lookback=lookback)

    def htf_labels(self, asof: datetime, i: int) -> dict[str, str]:
        labels = {"M15": "UNCERTAIN", "H1": "UNCERTAIN", "H4": "UNCERTAIN"}
        asof_ts = pd.Timestamp(asof)
        for tf in ("M15", "H1", "H4"):
            frame = self._htf.get(tf)
            if frame is None or frame.empty or "end" not in frame.columns:
                continue
            closed = frame.loc[frame["end"] <= asof_ts]
            if len(closed) < 5:
                continue
            labels[tf] = _trend_label(closed["close"])
        closes = self.df["close"].iloc[: i + 1]
        labels["M5"] = _trend_label(closes) if len(closes) >= 20 else "UNCERTAIN"
        return labels


def _research_from_prefix(ind: pd.DataFrame, adx_last: float | None) -> dict:
    last = ind.iloc[-1]
    atr = float(last["atr"]) if "atr" in last and last["atr"] == last["atr"] else None
    ma_fast = float(last["ma_fast"]) if last.get("ma_fast") == last.get("ma_fast") else None
    ma_slow = float(last["ma_slow"]) if last.get("ma_slow") == last.get("ma_slow") else None
    ema_sep_atr = None
    ema_slope = None
    if atr and atr > 0 and ma_fast is not None and ma_slow is not None:
        ema_sep_atr = (ma_fast - ma_slow) / atr
    if ma_fast is not None and len(ind) >= 6:
        prev = float(ind["ma_fast"].iloc[-6])
        if prev == prev:
            ema_slope = ma_fast - prev
    close = ind["close"].astype(float)
    recent = close.iloc[-12:] if len(close) >= 12 else close
    rng = float(recent.max() - recent.min()) if len(recent) else None
    recent_range_atr = (rng / atr) if rng is not None and atr and atr > 0 else None
    dist_mean = None
    if ma_slow is not None and atr and atr > 0:
        dist_mean = (float(close.iloc[-1]) - ma_slow) / atr
    atr_pct = atr_percentile(ind["atr"]) if "atr" in ind.columns else None
    adx = adx_last
    if adx is not None and (adx != adx):
        adx = None
    vol_state = "mid"
    if atr_pct is not None:
        if atr_pct >= 80:
            vol_state = "high"
        elif atr_pct <= 20:
            vol_state = "low"
    regime = classify_regime(adx=adx, ema_slope=ema_slope, ema_sep_atr=ema_sep_atr, atr_pct=atr_pct)
    rsi = float(last["rsi"]) if "rsi" in last and last["rsi"] == last["rsi"] else None
    macd = float(last["macd"]) if "macd" in last and last["macd"] == last["macd"] else None
    trend = float(last["trend"]) if "trend" in last and last["trend"] == last["trend"] else None
    return {
        "atr": atr,
        "atr_percentile": atr_pct,
        "ma_fast": ma_fast,
        "ma_slow": ma_slow,
        "rsi": rsi,
        "macd": macd,
        "trend": trend,
        "volatility": atr,
        "ema_slope": ema_slope,
        "ema_separation_atr": ema_sep_atr,
        "adx": adx,
        "distance_from_mean_atr": dist_mean,
        "recent_range_atr": recent_range_atr,
        "volatility_state": vol_state,
        "regime": regime,
    }


def evaluate_signal_cached(
    symbol: str,
    cache: SignalCache,
    i: int,
    now_utc: datetime,
    *,
    seed: int = 42,
    apply_session_hours: bool = False,
    apply_fx_week: bool = True,
    apply_volatility_filter: bool = True,
) -> DecisionSnapshot:
    """Same decision + snapshot fields as ``evaluate_signal`` on ``history_at(df, i)``."""
    reasons: list[str] = []
    route_lb = _env_int("HYBRID_ROUTE_LOOKBACK", 60)
    if apply_fx_week and not fx_market_open_at(now_utc):
        reasons.append("FX_WEEK_CLOSED")
        return _finish_snapshot(
            symbol, cache, i, now_utc, "", "", 0, "", "NO_SIGNAL", reasons, {}, None, None, None
        )
    if apply_session_hours and not in_active_session_at(symbol, now_utc):
        reasons.append("SESSION_HOURS_CLOSED")
        return _finish_snapshot(
            symbol, cache, i, now_utc, "", "", 0, "", "NO_SIGNAL", reasons, {}, None, None, None
        )

    df_route = cache.prefix_indicators(route_lb, i)
    strategy_name, lookback, horizon = seeded_select_strategy(symbol, df_route, seed)
    if strategy_name is None:
        reasons.append("NO_STRATEGY_ALLOCATION")
        return _finish_snapshot(
            symbol, cache, i, now_utc, "", "", 0, "", "NO_SIGNAL", reasons, {}, None, None, None
        )

    ind = cache.prefix_indicators(int(lookback), i)
    last = ind.iloc[-1]
    price = float(last["close"])
    ma_fast = float(last["ma_fast"]) if last["ma_fast"] == last["ma_fast"] else price
    ma_slow = float(last["ma_slow"]) if last["ma_slow"] == last["ma_slow"] else price
    atr_v = float(last["atr"]) if last["atr"] == last["atr"] else 0.0
    ret_1 = float(ind["close"].pct_change().iloc[-1]) if len(ind) > 1 else 0.0
    vote = _quant_stub_vote(
        {"price": price, "ma_fast": ma_fast, "ma_slow": ma_slow, "returns": ret_1, "atr": atr_v}
    )
    vote["price"] = price
    vote["atr"] = atr_v

    if apply_volatility_filter and not ind.empty and not volatility_ok(ind):
        reasons.append("VOLATILITY_FILTER")
        # Match evaluate_signal _blank: lookback field 0, empty vote, research at 50.
        return _finish_snapshot(
            symbol,
            cache,
            i,
            now_utc,
            strategy_name,
            horizon,
            0,
            "",
            "NO_SIGNAL",
            reasons,
            {},
            None,
            None,
            None,
        )

    if not vote.get("allow") or vote.get("direction") not in ("BUY", "SELL"):
        if vote.get("direction") is None:
            reasons.append("NO_SIGNAL_MA_FLAT")
        else:
            reasons.append("NO_SIGNAL_MOMENTUM_OR_ATR")
        return _finish_snapshot(
            symbol,
            cache,
            i,
            now_utc,
            strategy_name,
            horizon,
            int(lookback),
            "",
            "NO_SIGNAL",
            reasons,
            vote,
            None,
            None,
            None,
        )

    side = str(vote["direction"]).upper()
    atr = vote.get("atr")
    if atr is not None and (np.isnan(float(atr)) or float(atr) <= 0):
        atr = None
    sl, tp = sl_tp_from_production_distances(symbol, side, price, atr)
    reasons.append("QUANT_STUB_SIGNAL")
    return _finish_snapshot(
        symbol,
        cache,
        i,
        now_utc,
        strategy_name,
        horizon,
        int(lookback),
        side,
        side,
        reasons,
        vote,
        sl,
        tp,
        price,
    )


def _finish_snapshot(
    symbol: str,
    cache: SignalCache,
    i: int,
    now_utc: datetime,
    strategy: str,
    horizon: str,
    lookback: int,
    side: str,
    decision: str,
    reasons: list[str],
    vote: dict,
    stop_loss: float | None,
    take_profit: float | None,
    entry_price: float | None,
) -> DecisionSnapshot:
    raw = cache.df.iloc[: i + 1]
    mid = float(raw["close"].iloc[-1]) if not raw.empty else 0.0
    lb = lookback or 50
    ind = cache.prefix_indicators(int(lb), i) if cache.n else raw
    adx_val = None
    if i < len(cache._adx):
        adx_val = float(cache._adx.iloc[i])
        if adx_val != adx_val:
            adx_val = None
    # Prefix-correct ADX when indicator periods forced a prefix recompute of OHLC-identical
    # ADX still matches the precomputed series (OHLC-only). Keep series value.
    if _period_tuple(int(lb), i + 1) != _period_tuple(int(lb), cache.n):
        adx_val = wilder_adx(ind)
    research = _research_from_prefix(ind, adx_val)
    labels = cache.htf_labels(now_utc, i)
    atr = research.get("atr")
    spread = simulated_half_spread(symbol)
    pip = pip_size(symbol)
    spread_pips = spread / pip if pip else None
    spread_atr = (spread / atr) if atr and atr > 0 else None
    sl_d = abs(entry_price - stop_loss) if entry_price is not None and stop_loss is not None else None
    tp_d = abs(take_profit - entry_price) if entry_price is not None and take_profit is not None else None
    pre_move = pre_entry_extension_atr(raw, side or "BUY", atr) if side else None
    swing = distance_from_swing_atr(raw, side or "BUY", atr) if side else None
    return DecisionSnapshot(
        timestamp=now_utc,
        symbol=symbol,
        side=side,
        strategy=strategy,
        horizon=horizon,
        route="quant_stub+select_strategy",
        entry_price=float(entry_price) if entry_price is not None else mid,
        reference_mid=mid,
        decision=decision,
        reason_codes=list(reasons),
        lookback=lookback,
        atr=atr,
        atr_percentile=research.get("atr_percentile"),
        spread=spread,
        spread_pips=spread_pips,
        spread_over_atr=spread_atr,
        ma_fast=research.get("ma_fast"),
        ma_slow=research.get("ma_slow"),
        rsi=research.get("rsi"),
        macd=research.get("macd"),
        trend=research.get("trend"),
        volatility=research.get("volatility"),
        ema_slope=research.get("ema_slope"),
        ema_separation_atr=research.get("ema_separation_atr"),
        adx=research.get("adx"),
        distance_from_mean_atr=research.get("distance_from_mean_atr"),
        recent_range_atr=research.get("recent_range_atr"),
        volatility_state=str(research.get("volatility_state") or ""),
        session=classify_session(now_utc),
        hour_utc=hour_utc(now_utc),
        hour_london=hour_london(now_utc),
        day_of_week=int(now_utc.weekday()),
        m5_trend=labels.get("M5", ""),
        m15_trend=labels.get("M15", ""),
        h1_trend=labels.get("H1", ""),
        h4_trend=labels.get("H4", ""),
        htf_agreement=htf_alignment(side, labels) if side else "",
        regime=str(research.get("regime") or ""),
        signal_confidence=float(vote["confidence"]) if vote.get("confidence") is not None else None,
        stop_loss=stop_loss,
        take_profit=take_profit,
        sl_distance=sl_d,
        tp_distance=tp_d,
        pre_move_atr=pre_move,
        dist_swing_atr=swing,
        research_only=True,
    )
