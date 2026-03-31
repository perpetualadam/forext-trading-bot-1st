"""Deterministic vs noisy ``nn_pred`` for AI payload (backtest vs live)."""

from __future__ import annotations

import os
import random


def compute_nn_pred(price: float, seq_pred: float) -> float:
    """
    Neural-net-style price hint passed to LLM payloads.

    - ``NN_PRED_MODE=noise`` — legacy: ``price + small uniform jitter``.
    - ``NN_PRED_MODE=seq`` — use sequence model output (reproducible).
    - ``NN_PRED_MODE=price`` — mid price only.
    - ``NN_PRED_MODE=zero`` — literal ``0.0`` (for strict LLM tests).
    - Default: **backtest** (``FOREX_BACKTEST=1``) → ``seq``; **live** → ``noise``.
    """
    mode = (os.getenv("NN_PRED_MODE") or "").strip().lower()
    p = float(price)
    s = float(seq_pred)

    if mode in ("zero", "0"):
        return 0.0
    if mode == "price":
        return p
    if mode == "seq":
        return s
    if mode in ("noise", "random"):
        return p + random.uniform(-0.0005, 0.0005)

    if os.getenv("FOREX_BACKTEST", "").strip().lower() in ("1", "true", "yes", "on"):
        return s
    return p + random.uniform(-0.0005, 0.0005)
