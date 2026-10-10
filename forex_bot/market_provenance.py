"""Fail-closed market-data provenance. A caller-supplied label cannot become live.

The seal is created only by the acquisition helpers in this module. A string,
JSON field, or CSV column that says OANDA_LIVE_VERIFIED is rejected.
Same-process code can still call the acquisition helper; that limit is documented.
"""

from __future__ import annotations

import hashlib
import math
import time
from datetime import datetime, timezone
from typing import Any

OANDA_LIVE_VERIFIED = "OANDA_LIVE_VERIFIED"
OANDA_HISTORICAL_VERIFIED = "OANDA_HISTORICAL_VERIFIED"
SYNTHETIC_TEST = "SYNTHETIC_TEST"
REPLAYED_DATA = "REPLAYED_DATA"
IMPORTED_UNVERIFIED = "IMPORTED_UNVERIFIED"
CACHED_UNVERIFIED = "CACHED_UNVERIFIED"
UNKNOWN = "UNKNOWN"

CANDLE_ENDPOINT = "GET /v3/instruments/{instrument}/candles"
PRICING_ENDPOINT = "GET /v3/accounts/pricing"
DECISION_ACQUISITION_MAX_AGE_SEC = 180.0
ORDER_ACQUISITION_MAX_AGE_SEC = 15.0
DECISION_BAR_MAX_AGE_SEC = 30 * 60.0
MODEL_VERSION = "market_provenance_v2"
PREVIOUS_MODEL_VERSION = "market_provenance_v1"
RAW_MARKET_COLUMNS = (
    "time",
    "open",
    "high",
    "low",
    "close",
    "complete",
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
    "volume",
)
REQUIRED_OHLC = ("time", "open", "high", "low", "close")

_SEAL = object()


class ProvenanceRejected(RuntimeError):
    """Unverified market data cannot authorise a production decision or order."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class Provenance:
    """Immutable acquisition record. Live status requires the private seal."""

    def __init__(
        self,
        classification: str,
        *,
        instrument: str,
        host: str,
        endpoint: str,
        content_sha256: str,
        acquired_mono: float,
        protected_columns: tuple[str, ...] = (),
        seal: object | None = None,
    ) -> None:
        if classification == OANDA_LIVE_VERIFIED and seal is not _SEAL:
            raise ProvenanceRejected("spoofed_live_classification")
        self.classification = classification
        self.instrument = instrument
        self.host = host
        self.endpoint = endpoint
        self.content_sha256 = content_sha256
        self.acquired_mono = float(acquired_mono)
        self.protected_columns = tuple(protected_columns)
        self.model_version = MODEL_VERSION
        self.sealed_live = classification == OANDA_LIVE_VERIFIED and seal is _SEAL

    @property
    def production_eligible(self) -> bool:
        return self.sealed_live and self.classification == OANDA_LIVE_VERIFIED


def _inst(value: str) -> str:
    return (value or "").strip().upper().replace("-", "_").replace("/", "_")


def _fingerprint(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _num(value: Any) -> str:
    return f"{float(value):.10f}"


def _canon_cell(value: Any) -> str:
    """Stable encoding. Missing, NaN, infinity, and numbers stay distinct."""
    if value is None:
        return "missing"
    if isinstance(value, bool):
        return "bool:1" if value else "bool:0"
    if isinstance(value, datetime):
        stamp = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return "ts:" + stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    if isinstance(value, (int, float)):
        num = float(value)
        if math.isnan(num):
            return "nan"
        if math.isinf(num):
            return "posinf" if num > 0 else "neginf"
        return f"num:{num:.10f}"
    if type(value).__module__ == "numpy":
        try:
            num = float(value)
        except (TypeError, ValueError):
            return "str:" + str(value)
        if math.isnan(num):
            return "nan"
        if math.isinf(num):
            return "posinf" if num > 0 else "neginf"
        return f"num:{num:.10f}"
    return "str:" + str(value)


def raw_market_columns(frame: Any) -> tuple[str, ...]:
    names = list(getattr(frame, "columns", []))
    return tuple(col for col in RAW_MARKET_COLUMNS if col in names)


def frame_digest(frame: Any, columns: tuple[str, ...]) -> str:
    """Digest every protected cell, in row order. Indicator columns are omitted."""
    lines = [MODEL_VERSION, str(len(frame)), ",".join(columns)]
    for index in range(len(frame)):
        row = frame.iloc[index]
        cells = [str(index)]
        for col in columns:
            cells.append(col + "=" + _canon_cell(row[col]))
        lines.append("|".join(cells))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def candle_fingerprint(frame: Any) -> str:
    columns = raw_market_columns(frame)
    if any(col not in columns for col in REQUIRED_OHLC):
        raise ProvenanceRejected("missing_protected_column")
    return frame_digest(frame, columns)


def quote_fingerprint(quote: Any) -> str:
    parts = [MODEL_VERSION, str(getattr(quote, "instrument", ""))]
    for name in ("bid", "ask", "closeout_bid", "closeout_ask"):
        if hasattr(quote, name):
            parts.append(name + "=" + _canon_cell(getattr(quote, name)))
        else:
            parts.append(name + "=absent")
    return _fingerprint(parts)


def untrusted(
    classification: str,
    *,
    instrument: str = "",
    host: str = "",
    endpoint: str = "",
    content_sha256: str = "",
) -> Provenance:
    """Public constructor. Refuses to mint a live classification."""
    if classification == OANDA_LIVE_VERIFIED:
        raise ProvenanceRejected("spoofed_live_classification")
    return Provenance(
        classification,
        instrument=instrument,
        host=host,
        endpoint=endpoint,
        content_sha256=content_sha256,
        acquired_mono=time.monotonic(),
        seal=None,
    )


def _live(
    *,
    instrument: str,
    host: str,
    endpoint: str,
    content_sha256: str,
    acquired_mono: float | None,
    protected_columns: tuple[str, ...] = (),
) -> Provenance:
    return Provenance(
        OANDA_LIVE_VERIFIED,
        instrument=instrument,
        host=host,
        endpoint=endpoint,
        content_sha256=content_sha256,
        acquired_mono=time.monotonic() if acquired_mono is None else acquired_mono,
        protected_columns=protected_columns,
        seal=_SEAL,
    )


def bind_live_frame(
    frame: Any,
    *,
    instrument: str,
    host: str,
    endpoint: str = CANDLE_ENDPOINT,
    acquired_mono: float | None = None,
) -> Any:
    columns = raw_market_columns(frame)
    frame.attrs["market_provenance"] = _live(
        instrument=instrument,
        host=host,
        endpoint=endpoint,
        content_sha256=frame_digest(frame, columns),
        acquired_mono=acquired_mono,
        protected_columns=columns,
    )
    return frame


def bind_historical_frame(frame: Any, *, instrument: str, host: str) -> Any:
    frame.attrs["market_provenance"] = untrusted(
        OANDA_HISTORICAL_VERIFIED,
        instrument=instrument,
        host=host,
        endpoint=CANDLE_ENDPOINT,
        content_sha256=candle_fingerprint(frame),
    )
    return frame


def bind_synthetic_frame(frame: Any) -> Any:
    frame.attrs["market_provenance"] = untrusted(SYNTHETIC_TEST, endpoint="synthetic_market")
    return frame


def bind_imported_frame(frame: Any, *, source: str) -> Any:
    frame.attrs["market_provenance"] = untrusted(
        IMPORTED_UNVERIFIED,
        instrument="",
        host="",
        endpoint=source,
        content_sha256="",
    )
    return frame


def bind_live_quote(
    quote: Any,
    *,
    instrument: str,
    host: str,
    endpoint: str = PRICING_ENDPOINT,
    acquired_mono: float | None = None,
) -> Any:
    bid = getattr(quote, "bid", None)
    ask = getattr(quote, "ask", None)
    try:
        bid_f = float(str(bid))
        ask_f = float(str(ask))
    except (TypeError, ValueError):
        quote.provenance = untrusted(UNKNOWN, instrument=instrument, host=host, endpoint=endpoint)
        return quote
    if not (bid_f > 0 and ask_f > 0 and bid_f <= ask_f):
        quote.provenance = untrusted(UNKNOWN, instrument=instrument, host=host, endpoint=endpoint)
        return quote
    quote.instrument = instrument
    quote.provenance = _live(
        instrument=instrument,
        host=host,
        endpoint=endpoint,
        content_sha256=quote_fingerprint(quote),
        acquired_mono=acquired_mono,
    )
    return quote


def downgrade_cached(quote: Any) -> Any:
    prov = getattr(quote, "provenance", None)
    instrument = getattr(prov, "instrument", "") if prov is not None else str(getattr(quote, "instrument", ""))
    quote.provenance = untrusted(CACHED_UNVERIFIED, instrument=instrument, endpoint="process_cache")
    return quote


def _official_host() -> str:
    from forex_bot.config import Config

    if Config.TRADING_MODE == "live":
        return "https://api-fxtrade.oanda.com"
    return "https://api-fxpractice.oanda.com"


def _bar_time(frame: Any) -> datetime | None:
    raw = frame.iloc[-1]["time"]
    if isinstance(raw, datetime):
        stamp = raw
    else:
        text = str(raw).replace("Z", "+00:00")
        try:
            stamp = datetime.fromisoformat(text)
        except ValueError:
            return None
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _check_live(
    prov: Any,
    *,
    instrument: str,
    fingerprint: str,
    endpoint: str,
    max_age_sec: float,
    now_mono: float | None,
) -> str | None:
    if prov is None:
        return "missing_provenance"
    if not isinstance(prov, Provenance):
        return "invalid_provenance"
    if not prov.sealed_live or prov.classification != OANDA_LIVE_VERIFIED:
        return prov.classification or "invalid_provenance"
    if getattr(prov, "model_version", "") != MODEL_VERSION:
        return "old_provenance_version"
    if _inst(prov.instrument) != _inst(instrument):
        return "unexpected_instrument"
    if prov.host != _official_host():
        return "unexpected_host"
    if prov.endpoint != endpoint:
        return "unexpected_endpoint"
    age = (time.monotonic() if now_mono is None else now_mono) - prov.acquired_mono
    if age > max_age_sec:
        return "stale_acquisition"
    if prov.content_sha256 != fingerprint:
        return "tampered_payload"
    return None


def provenance_from_label(_label: str) -> Provenance:
    """A caller-supplied classification string is never a trusted acquisition."""
    raise ProvenanceRejected("caller_supplied_label")


def decision_frame_rejection(
    frame: Any,
    symbol: str,
    *,
    now: datetime | None = None,
    now_mono: float | None = None,
) -> str | None:
    if frame is None or getattr(frame, "empty", True):
        return "missing_provenance"
    prov = getattr(frame, "attrs", {}).get("market_provenance")
    try:
        for col in ("open", "high", "low", "close"):
            if col not in frame.columns:
                return "missing_protected_column"
            for index in range(len(frame)):
                val = float(frame.iloc[index][col])
                if not math.isfinite(val):
                    return "nonfinite_price"
                if val <= 0:
                    return "invalid_price"
        if isinstance(prov, Provenance) and prov.sealed_live:
            sealed = tuple(prov.protected_columns)
            current = raw_market_columns(frame)
            if not sealed:
                return "incomplete_seal"
            if current != sealed:
                if any(col not in current for col in sealed):
                    return "missing_protected_column"
                return "unexpected_protected_column"
            fingerprint = frame_digest(frame, sealed)
        else:
            fingerprint = candle_fingerprint(frame)
    except (KeyError, TypeError, ValueError, ProvenanceRejected):
        return "invalid_price"
    reason = _check_live(
        prov,
        instrument=symbol,
        fingerprint=fingerprint,
        endpoint=CANDLE_ENDPOINT,
        max_age_sec=DECISION_ACQUISITION_MAX_AGE_SEC,
        now_mono=now_mono,
    )
    if reason:
        return reason
    stamp = _bar_time(frame)
    if stamp is None:
        return "invalid_timestamp"
    clock = now or datetime.now(timezone.utc)
    if stamp > clock:
        return "future_timestamp"
    if (clock - stamp).total_seconds() > DECISION_BAR_MAX_AGE_SEC:
        return "stale_bar"
    return None


def order_quote_rejection(quote: Any, symbol: str, *, now_mono: float | None = None) -> str | None:
    if quote is None:
        return "missing_provenance"
    bid = getattr(quote, "bid", None)
    ask = getattr(quote, "ask", None)
    try:
        bid_f = float(str(bid))
        ask_f = float(str(ask))
    except (TypeError, ValueError):
        return "invalid_bid_ask"
    if not math.isfinite(bid_f) or not math.isfinite(ask_f):
        return "nonfinite_price"
    if bid_f <= 0 or ask_f <= 0:
        return "invalid_bid_ask"
    if bid_f > ask_f:
        return "crossed_bid_ask"
    try:
        fingerprint = quote_fingerprint(quote)
    except (TypeError, ValueError):
        return "invalid_bid_ask"
    return _check_live(
        getattr(quote, "provenance", None),
        instrument=symbol,
        fingerprint=fingerprint,
        endpoint=PRICING_ENDPOINT,
        max_age_sec=ORDER_ACQUISITION_MAX_AGE_SEC,
        now_mono=now_mono,
    )


def mint_live_quote(
    symbol: str = "EUR_USD",
    *,
    bid: float = 1.1,
    ask: float = 1.1002,
    host: str | None = None,
    acquired_mono: float | None = None,
) -> Any:
    """Trusted-boundary helper for a quote acquired in this process. Not a label parser."""
    from types import SimpleNamespace

    quote = SimpleNamespace(instrument=_inst(symbol), bid=bid, ask=ask, tradeable=True)
    return bind_live_quote(
        quote,
        instrument=_inst(symbol),
        host=host if host is not None else _official_host(),
        acquired_mono=acquired_mono,
    )


def require_order_quote(quote: Any, symbol: str) -> None:
    reason = order_quote_rejection(quote, symbol)
    if reason:
        raise ProvenanceRejected(reason)
