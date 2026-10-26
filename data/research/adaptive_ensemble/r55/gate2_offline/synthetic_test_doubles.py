"""Offline connection doubles and synthetic response bytes.

These values are fixtures. They are not OANDA prices, account facts, or a GBP model.
Nothing in this module opens a socket.
"""

from __future__ import annotations

import json
import time

ACCOUNT = "SYNTHETIC-ACCOUNT-R55G2-NOT-REAL"
TOKEN = "SYNTHETIC-TOKEN-R55G2-NOT-REAL"
SIX = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)
_PRICES = {
    "EUR_USD": ("1.20200", "1.20240", "-4"),
    "GBP_USD": ("1.30300", "1.30320", "-4"),
    "AUD_USD": ("0.70700", "0.70730", "-4"),
    "USD_CAD": ("1.40400", "1.40450", "-4"),
    "USD_CHF": ("0.90900", "0.90910", "-4"),
    "USD_JPY": ("141.000", "141.060", "-2"),
}


class OfflineDouble:
    """Marker for an in-process test double. This is not a live connection."""

    offline_only = True

    def __init__(self) -> None:
        self.events: list[str] = []
        self.timeouts_seen: dict[str, float] = {}
        self.hosts: list[str] = []
        self.ports: list[int] = []
        self.paths: list[str] = []
        self.queries: list[dict[str, str]] = []
        self.auth_flags: list[bool] = []
        self.chunks_read = 0
        self.closed = False

    def resolve(self, host: str, port: int, timeout: float) -> None:
        self.hosts.append(host)
        self.ports.append(port)
        self._block("resolve", timeout)

    def connect(self, timeout: float) -> None:
        self._block("connect", timeout)

    def handshake(self, timeout: float) -> None:
        self._block("handshake", timeout)

    def send_get(self, path: str, query: dict[str, str], timeout: float, authorization_present: bool) -> None:
        self.paths.append(path)
        self.queries.append(dict(query))
        self.auth_flags.append(bool(authorization_present))
        self._block("send", timeout)

    def read_headers(self, timeout: float) -> int:
        self._block("headers", timeout)
        return 200

    def read_chunk(self, timeout: float, max_chunk: int) -> bytes:
        self._block("chunk", timeout)
        self.chunks_read += 1
        return b""

    def close(self) -> None:
        self.closed = True

    def _block(self, phase: str, timeout: float) -> None:
        self.events.append(phase)
        self.timeouts_seen[phase] = timeout


class ScriptedDouble(OfflineDouble):
    """Double that can stall one phase or return a prepared status and body."""

    def __init__(
        self,
        status: int = 200,
        body: bytes = b"",
        stall_phase: str | None = None,
        stall_seconds: float = 0.0,
        ignore_timeout: bool = False,
        pause_each: float = 0.0,
        chunk_pause: float = 0.0,
        chunk_size: int = 65536,
    ) -> None:
        super().__init__()
        self._status = status
        self._body = bytes(body)
        self.stall_phase = stall_phase
        self.stall_seconds = stall_seconds
        self.ignore_timeout = ignore_timeout
        self.pause_each = pause_each
        self.chunk_pause = chunk_pause
        self.chunk_size = chunk_size
        self._offset = 0

    def read_headers(self, timeout: float) -> int:
        self._block("headers", timeout)
        return self._status

    def read_chunk(self, timeout: float, max_chunk: int) -> bytes:
        self.events.append("chunk")
        self.timeouts_seen["chunk"] = timeout
        self.chunks_read += 1
        if self.chunk_pause > 0:
            self._sleep_bound(self.chunk_pause, timeout)
        if self._offset >= len(self._body):
            return b""
        take = min(self.chunk_size, max_chunk, len(self._body) - self._offset)
        part = self._body[self._offset : self._offset + take]
        self._offset += take
        return part

    def _block(self, phase: str, timeout: float) -> None:
        super()._block(phase, timeout)
        limit = timeout if isinstance(timeout, (int, float)) else 0.0
        if self.stall_phase == phase:
            if self.ignore_timeout:
                time.sleep(self.stall_seconds)
                return
            self._sleep_bound(self.stall_seconds, limit)
            return
        if self.pause_each > 0 and self.stall_phase is None:
            self._sleep_bound(self.pause_each, limit)

    def _sleep_bound(self, want: float, limit: float) -> None:
        cap = limit if want > limit else want
        start = time.monotonic()
        while time.monotonic() - start < cap:
            remaining = cap - (time.monotonic() - start)
            if remaining <= 0:
                break
            time.sleep(min(0.02, remaining))
        if want > limit:
            raise TimeoutError()


def instrument_row(name: str, index: int) -> dict:
    pip = _PRICES[name][2]
    return {
        "name": name,
        "type": "CURRENCY",
        "pipLocation": pip,
        "displayPrecision": 3 if name.endswith("JPY") else 5,
        "minimumTradeSize": "1",
        "marginRate": f"0.06{index}",
        "financing": {"longRate": f"-0.03{index}", "shortRate": f"0.04{index}"},
    }


def instruments_payload() -> dict:
    return {"instruments": [instrument_row(name, index) for index, name in enumerate(SIX, start=1)]}


def price_row(name: str, index: int) -> dict:
    bid, ask, _pip = _PRICES[name]
    return {
        "instrument": name,
        "time": "2018-06-07T08:09:10Z",
        "tradeable": True,
        "bids": [{"price": bid}, {"price": "9.999"}],
        "asks": [{"price": ask}, {"price": "9.998"}],
        "quoteHomeConversionFactors": {
            "positiveUnits": f"0.91{index}",
            "negativeUnits": f"0.92{index}",
        },
        "homeConversions": [
            {"currency": "XTS", "accountGain": f"0.81{index}", "accountLoss": f"0.82{index}"}
        ],
    }


def pricing_payload() -> dict:
    return {"prices": [price_row(name, index) for index, name in enumerate(SIX, start=1)]}


def instruments_bytes() -> bytes:
    return json.dumps(instruments_payload()).encode("utf-8")


def pricing_bytes() -> bytes:
    return json.dumps(pricing_payload()).encode("utf-8")
