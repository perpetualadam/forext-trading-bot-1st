"""Offline checks for the frozen R.32 diagnostic calculations."""

from __future__ import annotations

import importlib.util
import socket
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R32_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R32_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = _dotenv

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "research" / "adaptive_ensemble" / "r32" / "diagnostics.py"
spec = importlib.util.spec_from_file_location("r32_diagnostics_test", PATH)
diag = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(diag)


def _trade(direction: str, entry: float, entry_mid: float, exit_price: float, exit_mid: float, reason: str, units: float = 10000.0) -> dict:
    return {
        "direction": direction,
        "entry_price": entry,
        "entry_mid": entry_mid,
        "exit_price": exit_price,
        "exit_mid": exit_mid,
        "exit_reason": reason,
        "units": units,
    }


def test_quote_exit_spread_is_the_execution_difference() -> None:
    trade = _trade("BUY", 1.1002, 1.1001, 1.1010, 1.1012, "signal_reversal")
    part = diag.attribute_trade(trade)
    assert abs(part["residual"]) < 1e-12
    assert abs(part["quoted"] - (part["price_movement"] + part["execution_difference"])) < 1e-12
    assert part["exit_spread_observed"] is True
    assert abs(part["spread_component"] - (-3.0)) < 1e-12


def test_order_exit_does_not_invent_an_exit_spread() -> None:
    trade = _trade("BUY", 1.1002, 1.1001, 1.0981, 1.0981, "stop")
    part = diag.attribute_trade(trade)
    assert part["exit_spread_observed"] is False
    assert abs(part["residual"]) < 1e-12
    assert abs(part["spread_component"] - (-1.0)) < 1e-12
    assert abs(part["exit_half"]) < 1e-12


def test_flat_market_is_symmetric_for_long_and_short() -> None:
    long_trade = _trade("BUY", 1.1002, 1.1001, 1.1000, 1.1001, "signal_reversal", units=50000)
    short_trade = _trade("SELL", 1.1000, 1.1001, 1.1002, 1.1001, "signal_reversal", units=50000)
    long_part = diag.attribute_trade(long_trade)
    short_part = diag.attribute_trade(short_trade)
    assert abs(long_part["price_movement"]) < 1e-12
    assert abs(short_part["price_movement"]) < 1e-12
    assert abs(long_part["quoted"] - short_part["quoted"]) < 1e-9
    assert long_part["quoted"] < 0


def test_direction_adjusted_return_flips_with_the_label() -> None:
    assert abs(diag.direction_adjusted("BUY", 1.10, 1.11) - 0.01) < 1e-12
    assert abs(diag.direction_adjusted("SELL", 1.10, 1.11) + 0.01) < 1e-12


def test_gapped_horizon_is_missing_and_windows_do_not_overlap() -> None:
    start = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=5 * index) for index in range(6)]
    times.append(times[-1] + timedelta(minutes=15))
    assert diag.horizon_complete(times, 0, 2) is True
    assert diag.horizon_complete(times, 4, 2) is False
    kept = diag.select_nonoverlapping([0, 5, 10, 12], 12, lambda index, horizon: index + horizon < 40)
    assert kept == [0, 12]


def test_shuffle_preserves_an_all_buy_sample_and_repeats() -> None:
    raw = [0.01, -0.02, 0.04]
    labels = ["BUY", "BUY", "BUY"]
    first = diag.shuffle_means(raw, labels, 32001, 15)
    second = diag.shuffle_means(raw, labels, 32001, 15)
    assert np.array_equal(first, second)
    assert np.allclose(first, np.mean(raw))
    coin = diag.coin_means(raw, 32101, 15)
    assert np.array_equal(coin, diag.coin_means(raw, 32101, 15))


def test_quarters_use_the_frozen_windows() -> None:
    assert diag.quarter_name(datetime(2026, 1, 15, tzinfo=timezone.utc)) == "2025-12_2026-02"
    assert diag.quarter_name(datetime(2026, 8, 31, 23, tzinfo=timezone.utc)) == "2026-06_2026-08"
    assert diag.quarter_name(datetime(2024, 1, 1, tzinfo=timezone.utc)) is None


def test_bootstrap_interval_repeats_and_refuses_a_short_sample() -> None:
    values = [0.01] * 20
    assert diag.block_interval(values[:19], 32201) is None
    first = diag.block_interval(values, 32201, replicates=30)
    second = diag.block_interval(values, 32201, replicates=30)
    assert first == second
    assert first is not None and abs(first[0] - 0.01) < 1e-12


def test_decision_rules_follow_the_protocol() -> None:
    quarters = [{"count": 40, "mean": 0.01} for _ in range(4)]
    interval = (0.001, 0.02)
    assert diag.decide(-0.01, 0.02, interval, 0.0, 0.0, 0.0001, quarters)["decision"] == "STOP_RESEARCH"
    assert diag.decide(0.01, -0.01, interval, 0.0, 0.0, 0.0001, quarters)["decision"] == "INCONCLUSIVE"
    assert diag.decide(0.01, 0.02, ( -0.001, 0.02), 0.0, 0.0, 0.0001, quarters)["decision"] == "INCONCLUSIVE"
    assert diag.decide(0.01, 0.02, interval, 0.0, 0.0, 0.0001, quarters)["decision"] == "CONTINUE_RESEARCH"
    assert diag.decide(0.00005, 0.00004, (0.00001, 0.00008), 0.0, 0.0, 0.0001, quarters)["decision"] == "STOP_RESEARCH"
    weak_quarters = [{"count": 40, "mean": 0.01}, {"count": 40, "mean": 0.01}, {"count": 40, "mean": -0.01}, {"count": 10, "mean": 0.01}]
    assert diag.decide(0.01, 0.02, interval, 0.0, 0.0, 0.0001, weak_quarters)["decision"] == "STOP_RESEARCH"


def test_open_exit_ignores_the_exit_bar_and_a_gap_is_flagged() -> None:
    start = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
    frame = pd.DataFrame(
        [
            {"bid_open": 1.10, "ask_open": 1.1002, "bid_high": 1.1020, "bid_low": 1.0990, "ask_high": 1.1022, "ask_low": 1.0992, "bid_close": 1.1010, "ask_close": 1.1012, "_time": start},
            {"bid_open": 1.11, "ask_open": 1.1102, "bid_high": 1.20, "bid_low": 1.0, "ask_high": 1.20, "ask_low": 1.0, "bid_close": 1.11, "ask_close": 1.1102, "_time": start + timedelta(minutes=5)},
            {"bid_open": 1.12, "ask_open": 1.1202, "bid_high": 1.12, "bid_low": 1.12, "ask_high": 1.13, "ask_low": 1.11, "bid_close": 1.12, "ask_close": 1.1202, "_time": start + timedelta(minutes=20)},
        ]
    )
    opened = diag.excursion(frame, {"direction": "BUY", "entry_index": 0, "exit_index": 1, "entry_price": 1.1002, "exit_reason": "signal_reversal"})
    assert abs(opened["mfe"] - (1.1020 - 1.1002)) < 1e-12
    assert opened["intrabar_order_unknown"] is False
    stopped = diag.excursion(frame, {"direction": "BUY", "entry_index": 0, "exit_index": 0, "entry_price": 1.1002, "exit_reason": "stop"})
    assert stopped["intrabar_order_unknown"] is True
    assert stopped["path_bars"] == 1
    gapped = diag.excursion(frame, {"direction": "SELL", "entry_index": 1, "exit_index": 2, "entry_price": 1.11, "exit_reason": "end_of_data"})
    assert gapped["unobserved_interval"] is True
