"""Offline chronological replay. No broker access. Opt-in via ShadowConfig.enabled."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.shadow.config import ShadowConfig
from forex_bot.shadow.engine import ShadowEngine
from forex_bot.shadow.store import ShadowStore
from forex_bot.symbols import normalize_oanda_symbol


def _as_utc(ts: object) -> datetime:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        return t.to_pydatetime().replace(tzinfo=timezone.utc)
    return t.tz_convert("UTC").to_pydatetime()


def split_periods(
    frame: pd.DataFrame,
    *,
    train_frac: float = 0.4,
    tune_frac: float = 0.2,
) -> dict[str, pd.DataFrame]:
    """Time-ordered split. Evaluation is the remainder. No shuffling."""
    n = len(frame)
    a = int(n * train_frac)
    b = int(n * (train_frac + tune_frac))
    return {
        "train": frame.iloc[:a].copy(),
        "tune": frame.iloc[a:b].copy(),
        "evaluate": frame.iloc[b:].copy(),
    }


def replay_symbol(
    engine: ShadowEngine,
    symbol: str,
    bars: pd.DataFrame,
    *,
    gbp_usd: pd.Series | None = None,
) -> ShadowEngine:
    """Walk bars in order. Decision at bar i uses only bars[:i+1]. Fill at bar i open."""
    engine.cfg.require_enabled()
    symbol = normalize_oanda_symbol(symbol)
    work = bars.copy()
    if "time" not in work.columns:
        raise ValueError("bars need a time column")
    work = work.sort_values("time").reset_index(drop=True)
    for i in range(len(work)):
        history = work.iloc[: i + 1]
        row = work.iloc[i]
        ts = _as_utc(row["time"])
        fx = None
        if gbp_usd is not None and i < len(gbp_usd):
            try:
                fx = float(gbp_usd.iloc[i])
            except (TypeError, ValueError):
                fx = None
        engine.process_symbol_bar(
            symbol=symbol,
            history=history,
            bar_time=ts,
            fill_open=float(row["open"]),
            gbp_usd_mid=fx,
        )
        engine.persist()
    return engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SIMULATED shadow replay — not live trading")
    parser.add_argument("--csv", required=True, help="OHLCV CSV with time,open,high,low,close")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--out", required=True, help="Directory for simulated JSONL/state")
    parser.add_argument(
        "--i-understand-this-is-simulated",
        action="store_true",
        help="Required. Enables shadow replay (still cannot place broker orders).",
    )
    args = parser.parse_args(argv)
    if not args.i_understand_this_is_simulated:
        raise SystemExit("refusing: pass --i-understand-this-is-simulated")
    frame = pd.read_csv(args.csv)
    cfg = ShadowConfig(enabled=True, store_dir=Path(args.out))
    store = ShadowStore(Path(args.out))
    engine = ShadowEngine(cfg=cfg, store=store)
    replay_symbol(engine, args.symbol, frame)
    print(engine.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
