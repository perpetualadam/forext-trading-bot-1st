"""Broker-disconnected shadow engine. Opt-in only. Never opens live exposure."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.shadow.accounting import (
    ShadowFill,
    ShadowPosition,
    conservative_intrabar_exit,
    executable_price,
    half_spread,
    mae_mfe_pips,
    quote_pnl_to_usd,
    stop_risk_gbp,
    units_for_notional,
    usd_direction,
    usd_to_gbp,
    utc_iso,
)
from forex_bot.shadow.config import ShadowConfig
from forex_bot.shadow.cost_model import COST_MODEL_VERSION, scenario_slip_multiplier
from forex_bot.shadow.reasons import STRATEGY_NAMES, ShadowReason
from forex_bot.shadow.risk import (
    quant_blocks,
    session_blocks_entry,
    spread_too_wide,
    utc_day_key,
    weekend_flatten,
)
from forex_bot.shadow.signals import (
    last_atr,
    lookback_for,
    prepare_frame,
    signal_from_arrays,
    signal_from_indicators,
    snapshot_features,
)
from forex_bot.shadow.store import ShadowStore
from forex_bot.shadow.tracks import TRACK_B, TRACK_B_LABEL
from forex_bot.symbols import normalize_oanda_symbol


def _opt_float(row: Any, key: str) -> float | None:
    try:
        val = row[key]
    except (KeyError, TypeError, IndexError):
        return None
    try:
        out = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(out):
        return None
    return out


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


@dataclass
class DecisionTrace:
    eval_time: datetime
    symbol: str
    strategy: str
    reason: str
    data_fresh: bool
    indicators_ready: bool
    candidate: str | None
    quant: str
    session: str
    risk: str
    eligible: bool
    opened: bool
    closed: bool
    detail: str = ""
    simulated: bool = True
    track: str = TRACK_B
    label: str = TRACK_B_LABEL
    fidelity: str = "N/A"
    cost_model_version: str = COST_MODEL_VERSION


@dataclass
class ShadowEngine:
    cfg: ShadowConfig
    store: ShadowStore | None = None
    equity_gbp: float = 0.0
    peak_equity_gbp: float = 0.0
    day_key: str = ""
    day_realised_gbp: float = 0.0
    positions: dict[tuple[str, str], ShadowPosition] = field(default_factory=dict)
    traces: list[DecisionTrace] = field(default_factory=list)
    fills: list[ShadowFill] = field(default_factory=list)
    seen_bar_keys: set[str] = field(default_factory=set)
    pending_entries: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    reason_counts: dict[str, int] = field(default_factory=dict)
    filled_this_bar: set[tuple[str, str]] = field(default_factory=set)
    indicator_cache: dict[int, pd.DataFrame] = field(default_factory=dict)
    feature_cache: dict[int, dict[str, Any]] = field(default_factory=dict)
    cursor: int | None = None

    def __post_init__(self) -> None:
        if self.equity_gbp <= 0:
            self.equity_gbp = float(self.cfg.starting_nav_gbp)
        if self.peak_equity_gbp <= 0:
            self.peak_equity_gbp = self.equity_gbp

    def restore(self) -> None:
        if self.store is None:
            return
        blob = self.store.read_state()
        if not blob:
            return
        self.equity_gbp = float(blob.get("equity_gbp") or self.cfg.starting_nav_gbp)
        self.peak_equity_gbp = float(blob.get("peak_equity_gbp") or self.equity_gbp)
        self.day_key = str(blob.get("day_key") or "")
        self.day_realised_gbp = float(blob.get("day_realised_gbp") or 0.0)
        self.seen_bar_keys = set(blob.get("seen_bar_keys") or [])
        self.pending_entries = {}
        self.positions = {}
        for raw in blob.get("positions") or []:
            if not isinstance(raw, dict):
                continue
            pos = ShadowPosition(
                symbol=str(raw["symbol"]),
                strategy=str(raw["strategy"]),
                direction=str(raw["direction"]),
                units=float(raw["units"]),
                entry_time=_as_utc(datetime.fromisoformat(str(raw["entry_time"]))),
                entry_mid=float(raw["entry_mid"]),
                entry_price=float(raw["entry_price"]),
                spread=float(raw["spread"]),
                slippage=float(raw["slippage"]),
                stop_loss=float(raw["stop_loss"]),
                take_profit=float(raw["take_profit"]),
                signal_bar_time=_as_utc(datetime.fromisoformat(str(raw["signal_bar_time"]))),
                fill_bar_time=_as_utc(datetime.fromisoformat(str(raw["fill_bar_time"]))),
                mae_pips=float(raw.get("mae_pips") or 0.0),
                mfe_pips=float(raw.get("mfe_pips") or 0.0),
            )
            self.positions[pos.key()] = pos

    def persist(self) -> None:
        if self.store is None:
            return
        self.store.write_state(
            {
                "equity_gbp": self.equity_gbp,
                "peak_equity_gbp": self.peak_equity_gbp,
                "day_key": self.day_key,
                "day_realised_gbp": self.day_realised_gbp,
                "seen_bar_keys": sorted(self.seen_bar_keys),
                "positions": [
                    {
                        "symbol": p.symbol,
                        "strategy": p.strategy,
                        "direction": p.direction,
                        "units": p.units,
                        "entry_time": utc_iso(p.entry_time),
                        "entry_mid": p.entry_mid,
                        "entry_price": p.entry_price,
                        "spread": p.spread,
                        "slippage": p.slippage,
                        "stop_loss": p.stop_loss,
                        "take_profit": p.take_profit,
                        "signal_bar_time": utc_iso(p.signal_bar_time),
                        "fill_bar_time": utc_iso(p.fill_bar_time),
                        "mae_pips": p.mae_pips,
                        "mfe_pips": p.mfe_pips,
                    }
                    for p in self.positions.values()
                ],
            }
        )

    def _trace(self, **kwargs: Any) -> DecisionTrace | None:
        reason = str(kwargs.get("reason") or "")
        self.reason_counts[reason] = self.reason_counts.get(reason, 0) + 1
        if not self.cfg.keep_traces:
            return None
        kwargs.setdefault("track", TRACK_B)
        kwargs.setdefault("label", self.cfg.result_label)
        kwargs.setdefault("fidelity", "N/A")
        kwargs.setdefault("cost_model_version", self.cfg.cost_model_version)
        tr = DecisionTrace(**kwargs)
        self.traces.append(tr)
        if self.store is not None:
            self.store.append_event({"kind": "trace", **tr.__dict__})
        return tr

    def _roll_day(self, ts: datetime) -> None:
        key = utc_day_key(ts)
        if key != self.day_key:
            self.day_key = key
            self.day_realised_gbp = 0.0

    def _drawdown_frac(self) -> float:
        if self.peak_equity_gbp <= 1e-12:
            return 0.0
        return max(0.0, (self.peak_equity_gbp - self.equity_gbp) / self.peak_equity_gbp)

    def _open_notional_gbp(self, gbp_usd: float | None) -> float:
        total = 0.0
        for p in self.positions.values():
            usd = quote_pnl_to_usd(p.symbol, abs(p.units) * p.entry_mid, p.entry_mid)
            # face value heuristic: units * mid in quote, converted like PnL path
            if p.symbol.endswith("_USD"):
                usd = abs(p.units) * p.entry_mid
            elif p.symbol.startswith("USD_"):
                usd = abs(p.units)
            total += usd_to_gbp(usd, gbp_usd, self.cfg)
        return total

    def _same_usd_count(self, direction_usd: str) -> int:
        n = 0
        for p in self.positions.values():
            if usd_direction(p.symbol, p.direction) == direction_usd:
                n += 1
        return n

    def process_symbol_bar(
        self,
        *,
        symbol: str,
        history: pd.DataFrame,
        bar_time: datetime,
        fill_open: float | None,
        gbp_usd_mid: float | None,
        bar: dict[str, Any] | None = None,
        prev_bar_time: datetime | None = None,
    ) -> None:
        self.cfg.require_enabled()
        symbol = normalize_oanda_symbol(symbol)
        ts = _as_utc(bar_time)
        self._roll_day(ts)
        bar_key = f"{symbol}|{utc_iso(ts)}"
        if bar_key in self.seen_bar_keys:
            for strategy in self.cfg.strategies:
                self._trace(
                    eval_time=ts,
                    symbol=symbol,
                    strategy=strategy,
                    reason=ShadowReason.DUPLICATE_BAR,
                    data_fresh=True,
                    indicators_ready=True,
                    candidate=None,
                    quant="skip",
                    session="skip",
                    risk="skip",
                    eligible=False,
                    opened=False,
                    closed=False,
                    detail="duplicate_candle",
                )
            return
        self.seen_bar_keys.add(bar_key)
        self.filled_this_bar.clear()

        stale = False
        if prev_bar_time is not None:
            gap = abs((ts - _as_utc(prev_bar_time)).total_seconds())
            stale = gap > self.cfg.stale_bar_seconds
        elif "time" in history.columns and len(history) >= 2:
            try:
                t0 = pd.Timestamp(history["time"].iloc[-2])
                t1 = pd.Timestamp(history["time"].iloc[-1])
                gap = abs((t1 - t0).total_seconds())
                if gap > self.cfg.stale_bar_seconds:
                    stale = True
            except (TypeError, ValueError):
                stale = False

        work = history
        if self.cfg.history_window > 0 and len(history) > self.cfg.history_window:
            work = history.iloc[-self.cfg.history_window :]

        row = bar if bar is not None else history.iloc[-1]
        high = float(row["high"])
        low = float(row["low"])
        o = float(row["open"])
        bid_o = _opt_float(row, "bid_open")
        ask_o = _opt_float(row, "ask_open")
        bid_h = _opt_float(row, "bid_high")
        bid_l = _opt_float(row, "bid_low")
        ask_h = _opt_float(row, "ask_high")
        ask_l = _opt_float(row, "ask_low")
        have_quotes = self.cfg.quote_aware and bid_o is not None and ask_o is not None

        if fill_open is not None:
            self._fill_pending(
                symbol,
                ts,
                float(fill_open),
                gbp_usd_mid,
                bid_open=bid_o,
                ask_open=ask_o,
            )

        for pos in list(self.positions.values()):
            if pos.symbol != symbol:
                continue
            pos.mae_pips, pos.mfe_pips = mae_mfe_pips(
                symbol, pos.direction, pos.entry_price, high, low, pos.mae_pips, pos.mfe_pips
            )
            if have_quotes and pos.direction == "BUY":
                o_q, h_q, l_q = bid_o or o, bid_h or high, bid_l or low
            elif have_quotes:
                o_q, h_q, l_q = ask_o or o, ask_h or high, ask_l or low
            else:
                o_q, h_q, l_q = o, high, low
            reason, px = conservative_intrabar_exit(
                pos.direction, pos.stop_loss, pos.take_profit, o_q, h_q, l_q
            )
            if reason is None and weekend_flatten(ts, self.cfg):
                reason, px = "weekend_flatten", float(row["close"])
            if reason is None or px is None:
                continue
            self._close(pos, ts, float(px), reason, gbp_usd_mid, float(row["close"]))

        session_reason = session_blocks_entry(ts, self.cfg)
        for strategy in self.cfg.strategies:
            self._consider_entry(
                symbol=symbol,
                strategy=strategy,
                history=work,
                ts=ts,
                stale=stale,
                session_reason=session_reason,
                gbp_usd_mid=gbp_usd_mid,
            )

    def _consider_entry(
        self,
        *,
        symbol: str,
        strategy: str,
        history: pd.DataFrame,
        ts: datetime,
        stale: bool,
        session_reason: str | None,
        gbp_usd_mid: float | None,
    ) -> None:
        key = (symbol, strategy)
        if key in self.positions or key in self.pending_entries:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.ALREADY_OPEN,
                data_fresh=not stale,
                indicators_ready=True,
                candidate=None,
                quant="n/a",
                session="n/a",
                risk="n/a",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        if stale:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.STALE_DATA,
                data_fresh=False,
                indicators_ready=False,
                candidate=None,
                quant="skip",
                session="skip",
                risk="skip",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        bars_ready = (
            self.cursor + 1
            if self.cursor is not None and self.feature_cache
            else len(history)
        )
        if bars_ready < self.cfg.min_bars:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.INSUFFICIENT_DATA,
                data_fresh=True,
                indicators_ready=False,
                candidate=None,
                quant="skip",
                session="skip",
                risk="skip",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        if session_reason:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=session_reason,
                data_fresh=True,
                indicators_ready=False,
                candidate=None,
                quant="skip",
                session="reject",
                risk="skip",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        lb = lookback_for(strategy, self.cfg.scalp_lookback, self.cfg.swing_lookback)
        pack = self.feature_cache.get(lb)
        df: pd.DataFrame | None = None
        ready = "ok"
        feats: dict[str, Any] = {}
        side: str | None
        detail: str
        atr: float
        mid: float
        if pack is not None and self.cursor is not None:
            i = self.cursor
            if i < 0 or i >= int(pack["n"]):
                self._trace(
                    eval_time=ts,
                    symbol=symbol,
                    strategy=strategy,
                    reason=ShadowReason.INSUFFICIENT_DATA,
                    data_fresh=True,
                    indicators_ready=False,
                    candidate=None,
                    quant="skip",
                    session="ok",
                    risk="skip",
                    eligible=False,
                    opened=False,
                    closed=False,
                )
                return
            if not bool(pack["quant_ok"][i]):
                self._trace(
                    eval_time=ts,
                    symbol=symbol,
                    strategy=strategy,
                    reason=ShadowReason.QUANT_REJECT,
                    data_fresh=True,
                    indicators_ready=True,
                    candidate=None,
                    quant="reject",
                    session="ok",
                    risk="skip",
                    eligible=False,
                    opened=False,
                    closed=False,
                )
                return
            side, detail = signal_from_arrays(strategy, i, pack)
            raw_atr = float(pack["atr"][i])
            atr = raw_atr if not math.isnan(raw_atr) and raw_atr > 0 else 0.0
            mid = float(pack["close"][i])
        else:
            cached = self.indicator_cache.get(lb)
            if cached is not None and self.cursor is not None:
                win = max(self.cfg.history_window, 250, lb + 5)
                start = max(0, self.cursor + 1 - win)
                df, ready = cached.iloc[start : self.cursor + 1], "ok"
            else:
                df, ready = prepare_frame(history, lb)
            feats = snapshot_features(df) if df is not None else {}
            if df is None:
                self._trace(
                    eval_time=ts,
                    symbol=symbol,
                    strategy=strategy,
                    reason=ready,
                    data_fresh=True,
                    indicators_ready=False,
                    candidate=None,
                    quant="skip",
                    session="ok",
                    risk="skip",
                    eligible=False,
                    opened=False,
                    closed=False,
                    detail=str(feats),
                )
                return
            q = quant_blocks(df)
            if q:
                self._trace(
                    eval_time=ts,
                    symbol=symbol,
                    strategy=strategy,
                    reason=q,
                    data_fresh=True,
                    indicators_ready=True,
                    candidate=None,
                    quant="reject",
                    session="ok",
                    risk="skip",
                    eligible=False,
                    opened=False,
                    closed=False,
                )
                return
            side, detail = signal_from_indicators(strategy, df)
            atr = last_atr(df)
            mid = float(df["close"].iloc[-1])
        if side is None:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=detail,
                data_fresh=True,
                indicators_ready=True,
                candidate=None,
                quant="ok",
                session="ok",
                risk="skip",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        hs = half_spread(symbol, self.cfg)
        if spread_too_wide(hs, atr, self.cfg):
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.SPREAD_REJECT,
                data_fresh=True,
                indicators_ready=True,
                candidate=side,
                quant="ok",
                session="ok",
                risk="reject",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        if self.day_realised_gbp <= -self.cfg.starting_nav_gbp * self.cfg.daily_loss_pct:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.DAILY_LOSS_LIMIT,
                data_fresh=True,
                indicators_ready=True,
                candidate=side,
                quant="ok",
                session="ok",
                risk="reject",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        if self._drawdown_frac() >= self.cfg.max_drawdown_pct:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.DRAWDOWN_LIMIT,
                data_fresh=True,
                indicators_ready=True,
                candidate=side,
                quant="ok",
                session="ok",
                risk="reject",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        if len(self.positions) + len(self.pending_entries) >= self.cfg.max_concurrent_positions:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.CONCURRENT_LIMIT,
                data_fresh=True,
                indicators_ready=True,
                candidate=side,
                quant="ok",
                session="ok",
                risk="reject",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        usd_dir = usd_direction(symbol, side)
        if usd_dir and self._same_usd_count(usd_dir) >= self.cfg.max_same_usd_direction:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.USD_CONCENTRATION,
                data_fresh=True,
                indicators_ready=True,
                candidate=side,
                quant="ok",
                session="ok",
                risk="reject",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        units = units_for_notional(symbol, mid, self.equity_gbp, self.cfg, gbp_usd_mid)
        if units < 1:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.SIZE_INFEASIBLE,
                data_fresh=True,
                indicators_ready=True,
                candidate=side,
                quant="ok",
                session="ok",
                risk="reject",
                eligible=False,
                opened=False,
                closed=False,
            )
            return
        sl_d = atr * self.cfg.sl_atr_mult if atr > 0 else hs * 20
        risk_gbp = stop_risk_gbp(symbol, mid, sl_d, units, gbp_usd_mid, self.cfg)
        if risk_gbp > self.equity_gbp * self.cfg.per_trade_risk_pct * 4:
            # hard cap vs tiny NAV: skip if stop risk is implausibly large vs 0.5% * 4 slack
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.RISK_REJECT,
                data_fresh=True,
                indicators_ready=True,
                candidate=side,
                quant="ok",
                session="ok",
                risk="reject",
                eligible=False,
                opened=False,
                closed=False,
                detail="per_trade_stop_risk",
            )
            return
        open_risk = sum(
            stop_risk_gbp(p.symbol, p.entry_mid, abs(p.entry_price - p.stop_loss), p.units, gbp_usd_mid, self.cfg)
            for p in self.positions.values()
        )
        if open_risk + risk_gbp > self.equity_gbp * self.cfg.max_portfolio_stop_risk_pct:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.RISK_REJECT,
                data_fresh=True,
                indicators_ready=True,
                candidate=side,
                quant="ok",
                session="ok",
                risk="reject",
                eligible=False,
                opened=False,
                closed=False,
                detail="aggregate_stop_risk",
            )
            return
        face = usd_to_gbp(
            abs(units) * mid if symbol.endswith("_USD") else abs(units),
            gbp_usd_mid,
            self.cfg,
        )
        if self._open_notional_gbp(gbp_usd_mid) + face > self.equity_gbp * self.cfg.max_portfolio_notional_pct:
            self._trace(
                eval_time=ts,
                symbol=symbol,
                strategy=strategy,
                reason=ShadowReason.RISK_REJECT,
                data_fresh=True,
                indicators_ready=True,
                candidate=side,
                quant="ok",
                session="ok",
                risk="reject",
                eligible=False,
                opened=False,
                closed=False,
                detail="notional_cap",
            )
            return
        sl = mid - sl_d if side == "BUY" else mid + sl_d
        tp = mid + sl_d * self.cfg.tp_risk_reward if side == "BUY" else mid - sl_d * self.cfg.tp_risk_reward
        self.pending_entries[key] = {
            "symbol": symbol,
            "strategy": strategy,
            "direction": side,
            "signal_time": ts,
            "signal_mid": mid,
            "atr": atr,
            "units": units,
            "sl": sl,
            "tp": tp,
            "detail": detail,
        }
        self._trace(
            eval_time=ts,
            symbol=symbol,
            strategy=strategy,
            reason=ShadowReason.SHADOW_ENTRY,
            data_fresh=True,
            indicators_ready=True,
            candidate=side,
            quant="ok",
            session="ok",
            risk="ok",
            eligible=True,
            opened=False,
            closed=False,
            detail=f"pending_next_open:{detail}",
        )

    def _fill_pending(
        self,
        symbol: str,
        fill_time: datetime,
        next_open: float,
        gbp_usd_mid: float | None,
        bid_open: float | None = None,
        ask_open: float | None = None,
    ) -> None:
        due = [k for k in self.pending_entries if k[0] == symbol]
        have_quotes = self.cfg.quote_aware and bid_open is not None and ask_open is not None
        slip_mult = scenario_slip_multiplier(self.cfg.cost_scenario, have_quotes=bool(have_quotes))
        for key in due:
            spec = self.pending_entries.pop(key)
            atr = float(spec["atr"])
            extra_slip = atr * self.cfg.slippage_atr_fraction * slip_mult if atr > 0 else 0.0
            if bid_open is not None and ask_open is not None and self.cfg.quote_aware:
                spread = (float(ask_open) - float(bid_open)) / 2.0
                if spec["direction"] == "BUY":
                    px = float(ask_open) + extra_slip
                else:
                    px = float(bid_open) - extra_slip
            else:
                px, spread, extra_slip = executable_price(
                    symbol,
                    spec["direction"],
                    float(next_open),
                    atr,
                    spec["strategy"],
                    self.cfg,
                    bid=bid_open,
                    ask=ask_open,
                )
            slip = extra_slip
            sl_d = abs(float(spec["signal_mid"]) - float(spec["sl"]))
            if spec["direction"] == "BUY":
                sl = px - sl_d
                tp = px + sl_d * self.cfg.tp_risk_reward
            else:
                sl = px + sl_d
                tp = px - sl_d * self.cfg.tp_risk_reward
            pos = ShadowPosition(
                symbol=symbol,
                strategy=spec["strategy"],
                direction=spec["direction"],
                units=float(spec["units"]),
                entry_time=fill_time,
                entry_mid=float(next_open),
                entry_price=px,
                spread=spread,
                slippage=slip,
                stop_loss=sl,
                take_profit=tp,
                signal_bar_time=spec["signal_time"],
                fill_bar_time=fill_time,
            )
            self.positions[key] = pos
            self.filled_this_bar.add(key)
            fill = ShadowFill(
                kind="entry",
                reason=ShadowReason.SHADOW_ENTRY,
                symbol=symbol,
                strategy=spec["strategy"],
                direction=spec["direction"],
                timestamp=fill_time,
                mid=float(next_open),
                price=px,
                units=pos.units,
                spread=spread,
                slippage=slip,
                stop_loss=sl,
                take_profit=tp,
                gross_gbp=0.0,
                costs_gbp=0.0,
                net_gbp=0.0,
            )
            self.fills.append(fill)
            if self.store is not None:
                self.store.append_event({"kind": "fill", **fill.__dict__})

    def _close(
        self,
        pos: ShadowPosition,
        ts: datetime,
        exit_mid: float,
        exit_reason: str,
        gbp_usd_mid: float | None,
        last_close: float,
    ) -> None:
        _ = last_close
        side_exit = "SELL" if pos.direction == "BUY" else "BUY"
        if self.cfg.quote_aware:
            px = float(exit_mid)
            spread = pos.spread
            slip = 0.0
        else:
            sl_atr = (
                abs(pos.entry_price - pos.stop_loss) / self.cfg.sl_atr_mult
                if self.cfg.sl_atr_mult
                else 0.0001
            )
            px, spread, slip = executable_price(
                pos.symbol, side_exit, float(exit_mid), sl_atr, pos.strategy, self.cfg
            )
        quote = (px - pos.entry_price) * pos.units if pos.direction == "BUY" else (pos.entry_price - px) * pos.units
        usd = quote_pnl_to_usd(pos.symbol, quote, px)
        net = usd_to_gbp(usd, gbp_usd_mid, self.cfg)
        cost_quote = (pos.spread + pos.slippage + spread + slip) * pos.units
        cost_gbp = usd_to_gbp(quote_pnl_to_usd(pos.symbol, cost_quote, px), gbp_usd_mid, self.cfg)
        self.equity_gbp += net
        self.peak_equity_gbp = max(self.peak_equity_gbp, self.equity_gbp)
        self.day_realised_gbp += net
        fill = ShadowFill(
            kind="exit",
            reason=ShadowReason.SHADOW_EXIT,
            symbol=pos.symbol,
            strategy=pos.strategy,
            direction=pos.direction,
            timestamp=ts,
            mid=float(exit_mid),
            price=px,
            units=pos.units,
            spread=spread,
            slippage=slip,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            gross_gbp=net + cost_gbp,
            costs_gbp=cost_gbp,
            net_gbp=net,
            mae_pips=pos.mae_pips,
            mfe_pips=pos.mfe_pips,
            exit_reason=exit_reason,
        )
        self.fills.append(fill)
        self.positions.pop(pos.key(), None)
        self._trace(
            eval_time=ts,
            symbol=pos.symbol,
            strategy=pos.strategy,
            reason=ShadowReason.SHADOW_EXIT,
            data_fresh=True,
            indicators_ready=True,
            candidate=pos.direction,
            quant="ok",
            session="ok",
            risk="ok",
            eligible=False,
            opened=False,
            closed=True,
            detail=exit_reason,
        )
        if self.store is not None:
            self.store.append_event({"kind": "fill", **fill.__dict__})

    def summary(self) -> dict[str, Any]:
        by: dict[str, dict[str, Any]] = {
            s: {"closes": 0, "net_gbp": 0.0, "wins": 0} for s in STRATEGY_NAMES
        }
        peak = self.cfg.starting_nav_gbp
        eq = self.cfg.starting_nav_gbp
        max_dd = 0.0
        for fill in self.fills:
            if fill.kind != "exit":
                continue
            row = by.setdefault(fill.strategy, {"closes": 0, "net_gbp": 0.0, "wins": 0})
            row["closes"] += 1
            row["net_gbp"] += fill.net_gbp
            if fill.net_gbp > 0:
                row["wins"] += 1
            eq += fill.net_gbp
            peak = max(peak, eq)
            max_dd = max(max_dd, peak - eq)
        return {
            "simulated": True,
            "label": self.cfg.label,
            "equity_gbp": self.equity_gbp,
            "max_dd_gbp": max_dd,
            "open_positions": len(self.positions),
            "by_strategy": by,
            "fills": len(self.fills),
        }
