"""Process-wide OANDA REST pacing. Official v20 cap is 120 requests/second."""

from __future__ import annotations

import os
import threading
import time

# OANDA REST documented ceiling. Never allow config above this.
OANDA_OFFICIAL_MAX_RPS = 120.0
# Default well under the ceiling so candles + reconcile + retries do not burst.
OANDA_DEFAULT_RPS = 10.0

_lock = threading.Lock()
_next_allowed = 0.0


def oanda_max_requests_per_sec() -> float:
    """Allowed REST rate. Always in ``[0.5, 120]``."""
    raw = (os.getenv("OANDA_MAX_REQUESTS_PER_SEC") or "").strip()
    if not raw:
        return OANDA_DEFAULT_RPS
    try:
        rps = float(raw)
    except ValueError:
        return OANDA_DEFAULT_RPS
    return max(0.5, min(float(OANDA_OFFICIAL_MAX_RPS), rps))


def reset_oanda_rate_limiter_for_tests() -> None:
    global _next_allowed
    with _lock:
        _next_allowed = 0.0


def acquire_oanda_rest_slot() -> float:
    """
    Block until this process may send one OANDA REST request.

    Shared by candles, account summary, reconcile, and order calls so they
    cannot stack above the configured rate.
    Returns seconds slept (0 if a slot was immediately available).
    """
    global _next_allowed
    interval = 1.0 / oanda_max_requests_per_sec()
    with _lock:
        now = time.monotonic()
        wait = max(0.0, _next_allowed - now)
        _next_allowed = max(now, _next_allowed) + interval
    if wait > 0.0:
        time.sleep(wait)
    return wait
