"""Rolling execution quality metrics (in-memory; reset on process restart)."""

from __future__ import annotations

import os
from collections import deque
from statistics import mean
from typing import Any


def _max_samples() -> int:
    try:
        return max(10, min(int((os.getenv("EXECUTION_METRICS_MAX_SAMPLES") or "500").strip() or "500"), 50_000))
    except ValueError:
        return 500


_slippage: deque[float] = deque(maxlen=_max_samples())
_latency_signal_to_send_ms: deque[float] = deque(maxlen=_max_samples())
_latency_send_to_fill_ms: deque[float] = deque(maxlen=_max_samples())
_fills_ok = 0
_fills_failed = 0


def record_fill_quality(
    *,
    expected_price: float,
    fill_price: float,
    direction: str,
    latency_signal_to_send_ms: float | None = None,
    latency_send_to_fill_ms: float | None = None,
) -> None:
    """Slippage in price space (signed: adverse positive for buys paying more)."""
    d = (direction or "").upper().strip()
    if d == "BUY":
        slip = float(fill_price) - float(expected_price)
    else:
        slip = float(expected_price) - float(fill_price)
    _slippage.append(slip)
    global _fills_ok
    _fills_ok += 1
    if latency_signal_to_send_ms is not None and latency_signal_to_send_ms >= 0:
        _latency_signal_to_send_ms.append(float(latency_signal_to_send_ms))
    if latency_send_to_fill_ms is not None and latency_send_to_fill_ms >= 0:
        _latency_send_to_fill_ms.append(float(latency_send_to_fill_ms))


def record_fill_failure() -> None:
    global _fills_failed
    _fills_failed += 1


def snapshot() -> dict[str, Any]:
    def _avg(d: deque[float]) -> float | None:
        return mean(d) if len(d) else None

    total = _fills_ok + _fills_failed
    return {
        "fills_succeeded": _fills_ok,
        "fills_failed": _fills_failed,
        "fill_success_rate": (_fills_ok / total) if total else None,
        "slippage_avg": _avg(_slippage),
        "slippage_samples": len(_slippage),
        "latency_signal_to_send_ms_avg": _avg(_latency_signal_to_send_ms),
        "latency_send_to_fill_ms_avg": _avg(_latency_send_to_fill_ms),
    }


def reset_for_tests() -> None:
    global _fills_ok, _fills_failed
    _slippage.clear()
    _latency_signal_to_send_ms.clear()
    _latency_send_to_fill_ms.clear()
    _fills_ok = 0
    _fills_failed = 0
