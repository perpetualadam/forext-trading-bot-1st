"""Full timestamp GBP conversion audit. Nominal amounts are not strategy profits."""

from __future__ import annotations

import hashlib
import math
from bisect import bisect_right
from datetime import datetime, timezone
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble.conversion import FxQuote, fixture_table
from forex_bot.research.adaptive_ensemble.g3_convert import convert_signed
from forex_bot.research.adaptive_ensemble.g4_gaps import PAIRS
from forex_bot.research.adaptive_ensemble.g4_sessions import session_label

NOMINAL = 1.0


class IndexedTable:
    """Bisect lookup with the same no-future rule as RateTable."""

    def __init__(self) -> None:
        self.times: dict[str, list[datetime]] = {}
        self.quotes: dict[str, list[FxQuote]] = {}

    def add_frame(self, pair: str, frame: pd.DataFrame) -> None:
        parsed = pd.to_datetime(frame["time"], utc=True)
        bids = pd.to_numeric(frame["bid_c"], errors="coerce")
        asks = pd.to_numeric(frame["ask_c"], errors="coerce")
        times: list[datetime] = []
        quotes: list[FxQuote] = []
        for i in range(len(frame)):
            bid = float(bids.iloc[i])
            ask = float(asks.iloc[i])
            if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask <= 0 or bid > ask:
                continue
            stamp = parsed.iloc[i].to_pydatetime().astimezone(timezone.utc).replace(microsecond=0)
            quote = FxQuote(stamp, pair, bid, ask, "oanda_m5_bid_ask")
            times.append(quote.time)
            quotes.append(quote)
        self.times[pair] = times
        self.quotes[pair] = quotes

    def last_at_or_before(self, pair: str, when: datetime) -> FxQuote | None:
        rows = self.times.get(pair)
        if not rows:
            return None
        limit = when.astimezone(timezone.utc) if when.tzinfo else when.replace(tzinfo=timezone.utc)
        idx = bisect_right(rows, limit) - 1
        if idx < 0:
            return None
        return self.quotes[pair][idx]


def strict_weekend(quote_time: datetime, when: datetime) -> bool:
    span_h = (when - quote_time).total_seconds() / 3600.0
    if quote_time.weekday() != 4 or not (24.0 < span_h <= 72.0):
        return False
    if when.weekday() == 6:
        return True
    return when.weekday() == 0 and when.hour < 12


def _expected(pair: str, amount: float) -> float:
    gbp = fixture_table().last_at_or_before("GBP_USD", datetime(2026, 9, 1, 12, tzinfo=timezone.utc))
    assert gbp is not None
    side_gbp = gbp.ask if amount >= 0 else gbp.bid
    if pair in {"EUR_USD", "GBP_USD", "AUD_USD"}:
        return amount / side_gbp
    cross_name = {"USD_JPY": "USD_JPY", "USD_CAD": "USD_CAD", "USD_CHF": "USD_CHF"}[pair]
    cross = fixture_table().last_at_or_before(cross_name, datetime(2026, 9, 1, 12, tzinfo=timezone.utc))
    assert cross is not None
    side = cross.ask if amount >= 0 else cross.bid
    return (amount / side) / side_gbp


def arithmetic_fixtures() -> dict[str, Any]:
    when = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    table = fixture_table()
    cases: list[dict[str, Any]] = []
    for pair in ("EUR_USD", "GBP_USD", "AUD_USD", "USD_JPY", "USD_CAD", "USD_CHF"):
        pos = convert_signed(pnl_quote=NOMINAL, pair=pair, when=when, table=table)
        neg = convert_signed(pnl_quote=-NOMINAL, pair=pair, when=when, table=table)
        cases.append(
            {
                "pair": pair,
                "positive_status": pos.status,
                "negative_status": neg.status,
                "positive_gbp": pos.gbp,
                "negative_gbp": neg.gbp,
                "positive_path": pos.path,
                "negative_path": neg.path,
                "expected_positive": _expected(pair, NOMINAL),
                "expected_negative": _expected(pair, -NOMINAL),
                "positive_uses_ask": any("ask" in step for step in pos.path),
                "negative_uses_bid": any("bid" in step for step in neg.path),
            }
        )
    ok = all(
        case["positive_status"] == "ok"
        and case["negative_status"] == "ok"
        and case["positive_uses_ask"]
        and case["negative_uses_bid"]
        and abs(float(case["positive_gbp"]) - float(case["expected_positive"])) < 1e-12
        and abs(float(case["negative_gbp"]) - float(case["expected_negative"])) < 1e-12
        and abs(float(case["negative_gbp"])) >= abs(float(case["positive_gbp"]))
        for case in cases
    )
    return {
        "nominal_quote_amount": NOMINAL,
        "strategy_pnl": False,
        "cases": cases,
        "passed": ok,
    }


def _bar_status(pos_status: str, neg_status: str, weekend_note: str | None, quote_time: datetime | None, when: datetime) -> str:
    if pos_status != "ok" or neg_status != "ok":
        if pos_status == "CONVERSION_STALE" or neg_status == "CONVERSION_STALE":
            return "stale"
        return "missing"
    if weekend_note == "weekend_last_quote":
        if quote_time is None or not strict_weekend(quote_time, when):
            return "stale"
        return "weekend_allowance"
    return "ok"


def audit_frames(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    table = IndexedTable()
    for pair, frame in frames.items():
        table.add_frame(pair, frame)
    digest = hashlib.sha256()
    per_pair: dict[str, Any] = {}
    failures: dict[str, set[str]] = {}
    session_rows: dict[str, dict[str, dict[str, int]]] = {}
    max_age_h = 0.0
    stale_examples: list[dict[str, str]] = []
    missing_examples: list[dict[str, str]] = []
    total = 0
    for pair in PAIRS:
        frame = frames[pair]
        parsed = pd.to_datetime(frame["time"], utc=True)
        counts = {"ok": 0, "weekend_allowance": 0, "stale": 0, "missing": 0, "bad_arithmetic": 0}
        sessions: dict[str, dict[str, int]] = {}
        for i in range(len(frame)):
            when = parsed.iloc[i].to_pydatetime().astimezone(timezone.utc).replace(microsecond=0)
            pos = convert_signed(pnl_quote=NOMINAL, pair=pair, when=when, table=table)  # type: ignore[arg-type]
            neg = convert_signed(pnl_quote=-NOMINAL, pair=pair, when=when, table=table)  # type: ignore[arg-type]
            quote_time = None
            if "GBP_USD" in pos.rate_times:
                quote_time = datetime.fromisoformat(pos.rate_times["GBP_USD"])
            status = _bar_status(pos.status, neg.status, pos.reason, quote_time, when)
            arithmetic_ok = (
                status in {"ok", "weekend_allowance"}
                and pos.gbp is not None
                and neg.gbp is not None
                and pos.gbp > 0
                and neg.gbp < 0
                and abs(neg.gbp) + 1e-9 >= abs(pos.gbp)
                and any("ask" in step for step in pos.path)
                and any("bid" in step for step in neg.path)
                and all(datetime.fromisoformat(value) <= when for value in pos.rate_times.values())
            )
            if status in {"ok", "weekend_allowance"} and not arithmetic_ok:
                status = "bad_arithmetic"
            if quote_time is not None:
                age_h = (when - quote_time).total_seconds() / 3600.0
                max_age_h = max(max_age_h, age_h)
            counts[status] = counts.get(status, 0) + 1
            session_day = session_label(when)
            key = "outside_session" if session_day is None else session_day.isoformat()
            bucket = sessions.setdefault(key, {"bars": 0, "ok": 0, "stale": 0, "missing": 0})
            bucket["bars"] += 1
            if status in {"ok", "weekend_allowance"}:
                bucket["ok"] += 1
            elif status == "stale":
                bucket["stale"] += 1
            else:
                bucket["missing"] += 1
            if status in {"stale", "missing", "bad_arithmetic"} and len(stale_examples) + len(missing_examples) < 30:
                item = {"pair": pair, "time": when.isoformat(), "status": status}
                if status == "stale":
                    stale_examples.append(item)
                else:
                    missing_examples.append(item)
            pos_gbp = 0.0 if pos.gbp is None else pos.gbp
            neg_gbp = 0.0 if neg.gbp is None else neg.gbp
            digest.update(f"{pair}|{when.isoformat()}|{status}|{pos_gbp:.8f}|{neg_gbp:.8f}".encode())
            total += 1
        failed = {key for key, bucket in sessions.items() if key != "outside_session" and bucket["ok"] != bucket["bars"]}
        failures[pair] = failed
        session_rows[pair] = sessions
        audited = sum(counts.values())
        per_pair[pair] = {
            **counts,
            "audited": audited,
            "coverage_pct": 100.0 * (counts["ok"] + counts["weekend_allowance"]) / audited if audited else 0.0,
        }
    status = "ok"
    if any(item["stale"] or item["missing"] or item["bad_arithmetic"] for item in per_pair.values()):
        status = "GBP_CONVERSION_UNVERIFIED"
    session_coverage = []
    session_keys = sorted({key for sessions in session_rows.values() for key in sessions if key != "outside_session"})
    for session_key in session_keys:
        bars = sum(session_rows[pair].get(session_key, {}).get("bars", 0) for pair in PAIRS)
        ok_bars = sum(session_rows[pair].get(session_key, {}).get("ok", 0) for pair in PAIRS)
        session_coverage.append(
            {
                "session": session_key,
                "bars": bars,
                "ok": ok_bars,
                "coverage_pct": 100.0 * ok_bars / bars if bars else 0.0,
            }
        )
    return {
        "status": status,
        "nominal_quote_amount": NOMINAL,
        "strategy_pnl": False,
        "full_portfolio_pnl_reconciliation": False,
        "estimated_rate_used": False,
        "timestamps_audited": total,
        "max_quote_age_hours": max_age_h,
        "per_pair": per_pair,
        "session_coverage": session_coverage,
        "conversion_failures": {pair: sorted(keys) for pair, keys in failures.items()},
        "stale_examples": stale_examples,
        "missing_examples": missing_examples,
        "digest_sha256": digest.hexdigest(),
        "routes": {
            "USD": "GBP_USD",
            "JPY": "USD_JPY then GBP_USD",
            "CAD": "USD_CAD then GBP_USD",
            "CHF": "USD_CHF then GBP_USD",
        },
        "positive_pnl": "buy the next currency at the ask",
        "negative_pnl": "cover the debit at the bid",
    }
