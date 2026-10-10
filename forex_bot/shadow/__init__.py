"""Broker-disconnected shadow evaluation. Disabled by default. Never executes live orders.

Importing this package must not load ``forex_bot.oanda_exec`` or ``forex_bot.trading``.
"""

from __future__ import annotations

from forex_bot.shadow.config import ShadowConfig
from forex_bot.shadow.engine import ShadowEngine
from forex_bot.shadow.original import TrackADecision, evaluate_original_bar
from forex_bot.shadow.reasons import ShadowReason
from forex_bot.shadow.tracks import TRACK_A, TRACK_B, TRACK_B_LABEL

__all__ = [
    "TRACK_A",
    "TRACK_B",
    "TRACK_B_LABEL",
    "ShadowConfig",
    "ShadowEngine",
    "ShadowReason",
    "TrackADecision",
    "evaluate_original_bar",
]
