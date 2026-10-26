"""Lifecycle tests. They do not score a trade."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from forex_bot.research.learning.lifecycle import apply_lifecycle, events_known_by, observation_row


def _candles(rows: list[tuple[int, float, float, float]]) -> pd.DataFrame:
    base = pd.Timestamp("2026-01-05T00:00:00Z")
    return pd.DataFrame(
        {
            "time": [base + pd.Timedelta(hours=hour - 1) for hour, *_rest in rows],
            "available_at": [base + pd.Timedelta(hours=hour) for hour, *_rest in rows],
            "bid_high": [item[1] for item in rows],
            "bid_low": [item[2] for item in rows],
            "bid_close": [item[3] for item in rows],
        }
    )


def _swing(kind: str, price: float, born: int, pivot: int = 0) -> dict:
    base = pd.Timestamp("2026-01-05T00:00:00Z")
    side = "HIGH" if kind == "RESISTANCE" else "LOW"
    pivot_time = base + pd.Timedelta(hours=pivot)
    return {
        "swing_id": f"{side}|EUR_USD|H1|{pivot_time.isoformat()}|{born}",
        "swing_type": side,
        "pivot_time": pivot_time,
        "pivot_price": price,
        "confirmation_time": base + pd.Timedelta(hours=born),
        "available_at": base + pd.Timedelta(hours=born),
        "instrument": "EUR_USD",
        "timeframe": "H1",
    }


def _line(kind: str, price: float, born: int, name: str) -> dict:
    base = pd.Timestamp("2026-01-05T00:00:00Z")
    return {
        "line_id": name,
        "line_type": kind,
        "first_pivot_time": base,
        "first_pivot_price": price,
        "slope_per_second": 0.0,
        "available_at": base + pd.Timedelta(hours=born),
        "source_swing_ids": [name],
    }


def _run(candles, swings=None, lines=None):
    return apply_lifecycle(
        candles,
        [] if swings is None else swings,
        [] if lines is None else lines,
        instrument="EUR_USD",
        timeframe="H1",
        pip_size=0.0001,
    )


def test_latest_pair_tie_break_and_crossed_levels() -> None:
    candles = _candles([(hour, 1.4, 1.2, 1.3) for hour in range(0, 6)])
    first = _swing("SUPPORT", 1.0, 1, 0)
    second = _swing("SUPPORT", 1.1, 3, 2)
    resistance = _swing("RESISTANCE", 1.5, 1, 0)
    result = _run(candles, [first, second, resistance])
    assert result["counts"]["levels_created"] == 3
    assert result["counts"]["level_supersessions"] == 1
    superseded = next(level for level in result["levels"] if level["price"] == 1.0)
    assert superseded["status"] == "SUPERSEDED"
    assert superseded["available_at"] == first["available_at"]
    active = [level for level in result["levels"] if level["status"] == "ACTIVE"]
    assert {level["price"] for level in active} == {1.1, 1.5}
    assert result["ranges"][-1]["support_price"] == 1.1
    assert result["ranges"][-1]["pair_available_at"] == second["available_at"]
    same_time = _run(candles, [_swing("SUPPORT", 1.0, 2, 0), _swing("RESISTANCE", 1.4, 2, 0)])
    assert same_time["counts"]["range_pairs"] == 1
    assert same_time["ranges"][0]["state"] == "CANDIDATE"
    crossed = _run(candles, [_swing("SUPPORT", 1.8, 1, 0), _swing("RESISTANCE", 1.2, 1, 0)])
    assert crossed["counts"]["range_pairs"] == 0
    assert crossed["counts"]["contradictory_pairs"] == 1
    assert crossed["counts"]["confirmed_ranges"] == 0
    assert all(row["range_state"] == "UNCERTAIN" for row in crossed["states"])


def test_level_and_line_lifecycle_are_causal() -> None:
    candles = _candles(
        [
            (0, 1.2, 1.1, 1.15),
            (1, 1.2, 0.5, 0.6),
            (2, 1.2, 0.4, 0.5),
            (3, 1.2, 1.0, 1.1),
            (4, 1.2, 0.8, 0.9),
        ]
    )
    support = _swing("SUPPORT", 1.0, 1, 0)
    result = _run(candles, [support])
    level = result["levels"][0]
    assert level["transitions"][0]["available_at"] == support["available_at"]
    assert level["status"] == "INVALIDATED"
    assert level["transitions"][-1]["available_at"] == pd.Timestamp("2026-01-05T02:00:00Z")
    assert result["counts"]["level_invalidations"] == 1
    hidden = events_known_by(result, pd.Timestamp("2026-01-05T00:30:00Z"))
    assert hidden == []
    line = _line("SUPPORT", 1.0, 1, "line-a")
    later = _line("SUPPORT", 1.0, 3, "line-b")
    lined = _run(candles, [], [line])
    assert lined["counts"]["trendline_breaks"] == 1
    assert lined["counts"]["trendline_supersessions"] == 0
    assert lined["lines"][0]["status"] == "BROKEN"
    assert lined["lines"][0]["available_at"] == line["available_at"]
    quiet = _candles([(hour, 1.3, 1.05, 1.1) for hour in range(0, 6)])
    superseded = _run(quiet, [], [line, later])
    assert superseded["lines"][0]["status"] == "SUPERSEDED"
    assert superseded["counts"]["trendline_breaks"] == 0
    assert superseded["lines"][0]["transitions"][0]["available_at"] == line["available_at"]


def test_touch_and_break_episodes_are_not_repeated() -> None:
    candles = _candles(
        [
            (1, 1.2, 0.9, 1.05),
            (2, 1.2, 0.9, 1.05),
            (3, 1.2, 0.9, 1.05),
            (4, 1.3, 1.15, 1.2),
            (5, 1.2, 0.9, 1.05),
            (6, 1.2, 0.7, 0.8),
            (7, 1.2, 0.6, 0.7),
        ]
    )
    result = _run(candles, [_swing("SUPPORT", 1.0, 0, 0)], [_line("SUPPORT", 1.0, 0, "line-a")])
    assert result["counts"]["support_touch_episodes"] == 2
    assert result["counts"]["line_touch_episodes"] == 2
    assert result["counts"]["trendline_breaks"] == 1
    assert result["counts"]["level_invalidations"] == 1
    assert result["counts"]["legacy_raw_continuation_comparisons"] == 0


def test_range_confirmation_invalidation_and_deduplicated_reactions() -> None:
    candles = _candles(
        [
            (0, 1.4, 1.2, 1.3),
            (1, 1.6, 1.0, 1.4),
            (2, 1.6, 1.0, 1.4),
            (3, 1.5, 1.2, 1.35),
            (4, 1.6, 0.95, 1.4),
            (5, 2.0, 1.4, 1.7),
            (6, 1.5, 1.3, 1.4),
            (7, 2.05, 1.4, 1.6),
            (8, 1.5, 1.3, 1.4),
            (9, 1.5, 0.4, 0.5),
        ]
    )
    result = _run(candles, [_swing("SUPPORT", 1.0, 0, 0), _swing("RESISTANCE", 2.0, 0, 0)])
    confirmed = result["ranges"][0]
    assert confirmed["state"] == "INVALIDATED"
    assert confirmed["confirmed_at"] == pd.Timestamp("2026-01-05T07:00:00Z")
    assert len(confirmed["support_reactions"]) == 2
    assert len(confirmed["resistance_reactions"]) == 2
    assert result["counts"]["confirmed_ranges"] == 1
    assert result["counts"]["range_invalidations"] == 1
    assert result["counts"]["confirmed_then_invalidated"] == 1
    assert confirmed["support_reactions"][0]["available_at"] > confirmed["pair_available_at"]
    early = _run(candles.iloc[:3].copy(), [_swing("SUPPORT", 1.0, 0, 0), _swing("RESISTANCE", 2.0, 0, 0)])
    assert early["counts"]["confirmed_ranges"] == 0
    assert early["counts"]["range_reaction_episodes"] == 1
    failed = _candles([(0, 1.4, 1.2, 1.3), (1, 1.6, 1.0, 1.4), (2, 1.2, 0.4, 0.5)])
    failed_result = _run(failed, [_swing("SUPPORT", 1.0, 0, 0), _swing("RESISTANCE", 2.0, 0, 0)])
    assert failed_result["counts"]["confirmed_ranges"] == 0
    assert failed_result["counts"]["invalidated_before_confirmation"] == 1
    assert failed_result["ranges"][0]["state"] == "INVALIDATED"


def test_prefix_hides_later_events_and_keeps_earlier_history() -> None:
    candles = _candles([(hour, 1.4, 1.05, 1.2) for hour in range(0, 8)])
    candles.loc[6, "bid_close"] = 0.8
    candles.loc[6, "bid_low"] = 0.7
    swings = [_swing("SUPPORT", 1.0, 1, 0), _swing("SUPPORT", 1.05, 4, 2), _swing("RESISTANCE", 1.5, 1, 0)]
    full = _run(candles, swings, [_line("SUPPORT", 1.2, 1, "line-a"), _line("SUPPORT", 1.25, 5, "line-b")])
    cutoff = pd.Timestamp("2026-01-05T03:00:00Z")
    prefix = _run(candles.loc[candles["available_at"] <= cutoff].copy(), [swings[0], swings[2]], [_line("SUPPORT", 1.2, 1, "line-a")])
    full_ids = [(row["event_type"], row["related_id"], row["available_at"]) for row in events_known_by(full, cutoff)]
    prefix_ids = [(row["event_type"], row["related_id"], row["available_at"]) for row in prefix["events"]]
    assert prefix_ids == full_ids
    assert full["levels"][0]["transitions"][0]["available_at"] == prefix["levels"][0]["transitions"][0]["available_at"]
    assert full["trading_signal"] is None
    row = observation_row(full["states"][0], "EUR_USD", "H1", "abc", "protocol")
    assert row["trading_decision"] is None
    assert row["outcome"] is None
    assert row["confidence"] is None
    from forex_bot.ai_ensemble import _quant_stub_vote
    from forex_bot.rl_agent import RLAgent
    from forex_bot.research.learning.data_validation import file_sha256
    from forex_bot.research.learning.regimes import DATASET_SHA256
    from forex_bot.strategy_meta import strategies

    assert file_sha256(Path("data/historical/EUR_USD_M5.csv")) == DATASET_SHA256["EUR_USD"]
    assert all(not item.active and not item.authorised_for_live for item in strategies.values())
    assert _quant_stub_vote({"returns": 1})["allow"] is False
    assert RLAgent().decide("unseen") == "UNAVAILABLE"
    bot = open("forex_bot/bot_loop.py", encoding="utf-8").read()
    assert "learning.lifecycle" not in bot
    assert "apply_lifecycle" not in bot
