"""Offline six-pair portfolio accounting. Not live concurrency. Not a profitability report."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from forex_bot.research.adaptive_ensemble.conversion import (
    GBP_CONVERSION_UNVERIFIED,
    ConversionResult,
    RateTable,
    convert_pnl,
)
from forex_bot.research.adaptive_ensemble.protocol import PROTOCOL, integrity_hash

PAIRS = list(PROTOCOL["pairs"])
SCHEMA = "portfolio_v2"
KIND_ORDER = {"exit": 0, "release": 1, "signal": 2, "fill": 3}
CHANGE_CLASS = "BEHAVIOURAL_REPAIR_REQUIRES_REBASELINE"


def _utc_day(ts: str) -> str:
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc).date().isoformat()


def usd_sign(pair: str, direction: str) -> int:
    buy = direction == "BUY"
    if pair.endswith("_USD"):
        return -1 if buy else 1
    if pair.startswith("USD_"):
        return 1 if buy else -1
    return 0


@dataclass
class Position:
    pair: str
    direction: str
    units: float
    entry: float
    entry_time: str


@dataclass
class Pending:
    pair: str
    direction: str
    units: float
    time: str


@dataclass
class PortfolioV2:
    schema: str = SCHEMA
    run_id: str = ""
    status: str = "ok"
    cash_gbp: float | None = 97.0
    peak_nav: float | None = 97.0
    start_nav: float = 97.0
    conversion_status: str = GBP_CONVERSION_UNVERIFIED
    open: dict[str, Position] = field(default_factory=dict)
    pending: dict[str, Pending] = field(default_factory=dict)
    realised_gbp: float = 0.0
    realised_by_day: dict[str, float] = field(default_factory=dict)
    halted: str | None = None
    daily_loss_halt_pct: float = 0.02
    max_dd_halt_pct: float = 0.05
    max_open: int = 2
    max_shared_usd_units: float = 2000.0
    seen_event_ids: list[str] = field(default_factory=list)

    def dump(self) -> dict[str, Any]:
        body = {
            "schema": self.schema,
            "run_id": self.run_id,
            "status": self.status,
            "cash_gbp": self.cash_gbp,
            "peak_nav": self.peak_nav,
            "start_nav": self.start_nav,
            "conversion_status": self.conversion_status,
            "open": {k: asdict(v) for k, v in self.open.items()},
            "pending": {k: asdict(v) for k, v in self.pending.items()},
            "realised_gbp": self.realised_gbp,
            "realised_by_day": dict(self.realised_by_day),
            "halted": self.halted,
            "daily_loss_halt_pct": self.daily_loss_halt_pct,
            "max_dd_halt_pct": self.max_dd_halt_pct,
            "max_open": self.max_open,
            "max_shared_usd_units": self.max_shared_usd_units,
            "seen_event_ids": list(self.seen_event_ids),
        }
        body["integrity_hash"] = integrity_hash(body)
        return body


def event_sort_key(event: dict[str, Any]) -> tuple[Any, ...]:
    pair = str(event.get("pair") or "")
    try:
        pidx = PAIRS.index(pair)
    except ValueError:
        pidx = 99
    kind = str(event.get("kind") or "signal")
    return (str(event.get("time") or ""), pidx, KIND_ORDER.get(kind, 9), int(event.get("seq") or 0))


def _usd_units(state: PortfolioV2) -> float:
    total = 0.0
    for pos in state.open.values():
        total += usd_sign(pos.pair, pos.direction) * pos.units
    for pend in state.pending.values():
        total += usd_sign(pend.pair, pend.direction) * pend.units
    return total


def can_reserve(state: PortfolioV2, pair: str, direction: str, units: float) -> str | None:
    if state.status != "ok":
        return state.status
    if state.halted:
        return state.halted
    if pair not in PAIRS:
        return "unknown_pair"
    if pair in state.open or pair in state.pending:
        return "duplicate_pair_exposure"
    occupied = len(state.open) + len(state.pending)
    if occupied >= state.max_open:
        return "position_cap"
    nxt = _usd_units(state) + usd_sign(pair, direction) * units
    if abs(nxt) > state.max_shared_usd_units:
        return "shared_usd_cap"
    return None


def reserve(state: PortfolioV2, *, pair: str, direction: str, units: float, time: str, event_id: str) -> str | None:
    if event_id in state.seen_event_ids:
        return "duplicate_event"
    reason = can_reserve(state, pair, direction, units)
    if reason:
        return reason
    state.pending[pair] = Pending(pair, direction, units, time)
    state.seen_event_ids.append(event_id)
    return None


def fill_pending(state: PortfolioV2, *, pair: str, entry: float, event_id: str, fraction: float = 1.0) -> str | None:
    if event_id in state.seen_event_ids:
        return "duplicate_event"
    pend = state.pending.get(pair)
    if pend is None:
        return "no_pending"
    if fraction <= 0:
        del state.pending[pair]
        state.seen_event_ids.append(event_id)
        return "zero_fill_released"
    units = pend.units * min(1.0, fraction)
    state.open[pair] = Position(pair, pend.direction, units, entry, pend.time)
    del state.pending[pair]
    state.seen_event_ids.append(event_id)
    return None


def release_pending(state: PortfolioV2, *, pair: str, event_id: str) -> None:
    if event_id in state.seen_event_ids:
        return
    state.pending.pop(pair, None)
    state.seen_event_ids.append(event_id)


def close_position(
    state: PortfolioV2,
    *,
    pair: str,
    exit_px: float,
    time: str,
    table: RateTable | None,
    event_id: str,
) -> ConversionResult | None:
    if event_id in state.seen_event_ids:
        return None
    pos = state.open.get(pair)
    if pos is None:
        return None
    signed = 1.0 if pos.direction == "BUY" else -1.0
    pnl_q = (exit_px - pos.entry) * signed * pos.units
    if table is None:
        state.conversion_status = GBP_CONVERSION_UNVERIFIED
        state.status = "GBP_CONVERSION_UNVERIFIED"
        del state.open[pair]
        state.seen_event_ids.append(event_id)
        return ConversionResult(GBP_CONVERSION_UNVERIFIED, None, [], {}, "UNAVAILABLE", "missing_table")
    conv = convert_pnl(pnl_quote=pnl_q, pair=pair, when=time, table=table)
    if conv.gbp is None:
        state.conversion_status = GBP_CONVERSION_UNVERIFIED
        state.status = GBP_CONVERSION_UNVERIFIED
        del state.open[pair]
        state.seen_event_ids.append(event_id)
        return conv
    state.conversion_status = "ok"
    state.realised_gbp += conv.gbp
    if state.cash_gbp is not None:
        state.cash_gbp += conv.gbp
    day = _utc_day(time)
    state.realised_by_day[day] = state.realised_by_day.get(day, 0.0) + conv.gbp
    nav = state.cash_gbp if state.cash_gbp is not None else state.start_nav + state.realised_gbp
    if state.peak_nav is None:
        state.peak_nav = nav
    else:
        state.peak_nav = max(state.peak_nav, nav)
    if conv.gbp <= -state.daily_loss_halt_pct * state.start_nav:
        state.halted = "daily_loss"
    day_pnl = state.realised_by_day[day]
    if day_pnl <= -state.daily_loss_halt_pct * state.start_nav:
        state.halted = "daily_loss"
    if state.peak_nav and (state.peak_nav - nav) / state.peak_nav >= state.max_dd_halt_pct:
        state.halted = "max_drawdown"
    del state.open[pair]
    state.seen_event_ids.append(event_id)
    return conv


def load_portfolio(blob: dict[str, Any]) -> PortfolioV2:
    if blob.get("schema") != SCHEMA:
        return PortfolioV2(status="MODEL_STATE_INCOMPATIBLE")
    if blob.get("integrity_hash") != integrity_hash(blob):
        return PortfolioV2(status="MODEL_STATE_INVALID")
    st = PortfolioV2(run_id=str(blob.get("run_id") or ""))
    st.cash_gbp = blob.get("cash_gbp")
    st.peak_nav = blob.get("peak_nav")
    st.start_nav = float(blob.get("start_nav") or 97.0)
    st.conversion_status = str(blob.get("conversion_status") or GBP_CONVERSION_UNVERIFIED)
    st.realised_gbp = float(blob.get("realised_gbp") or 0.0)
    st.realised_by_day = {str(k): float(v) for k, v in (blob.get("realised_by_day") or {}).items()}
    st.halted = blob.get("halted")
    st.seen_event_ids = list(blob.get("seen_event_ids") or [])
    for k, v in (blob.get("open") or {}).items():
        st.open[str(k)] = Position(**v)
    for k, v in (blob.get("pending") or {}).items():
        st.pending[str(k)] = Pending(**v)
    return st


def process_events(events: list[dict[str, Any]], *, run_id: str, table: RateTable | None) -> PortfolioV2:
    state = PortfolioV2(run_id=run_id, conversion_status="ok" if table is not None else GBP_CONVERSION_UNVERIFIED)
    for ev in sorted(events, key=event_sort_key):
        kind = ev["kind"]
        pair = ev["pair"]
        eid = str(ev.get("event_id") or f"{ev['time']}:{pair}:{kind}:{ev.get('seq')}")
        if kind == "signal":
            reserve(
                state,
                pair=pair,
                direction=ev["direction"],
                units=float(ev.get("units") or 1000.0),
                time=str(ev["time"]),
                event_id=eid,
            )
        elif kind == "fill":
            fill_pending(
                state,
                pair=pair,
                entry=float(ev["entry"]),
                event_id=eid,
                fraction=float(ev.get("fraction") or 1.0),
            )
        elif kind == "release":
            release_pending(state, pair=pair, event_id=eid)
        elif kind == "exit":
            close_position(
                state,
                pair=pair,
                exit_px=float(ev["exit_px"]),
                time=str(ev["time"]),
                table=table,
                event_id=eid,
            )
    return state


def dumps(state: PortfolioV2) -> str:
    return json.dumps(state.dump(), indent=2, sort_keys=True)
