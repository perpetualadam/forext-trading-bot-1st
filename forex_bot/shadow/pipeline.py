"""Live vs shadow decision-pipeline map (documentation only; no runtime side effects).

Live ``evaluate()`` in ``bot_loop.py`` (side effects noted):

1. ``fetch_ohlcv`` — network I/O (OANDA candles GET; not an order).
2. Empty-frame check — pure.
3. ``record_mid`` / v2 shadow persist — live side effects; not used by this package.
4. Session / weekend flatten for *new* entries — mostly pure (``session_rules``).
5. Open-position management — live SL/TP/profit-protection; may ``PositionClose``.
6. Pending broker-exit gate — live.
7. ``pre_trade_entry_blocked_reason()`` — **LIVE_ORDER_AUTH_BLOCKED stops here**
   before indicators, strategy selection, quant, sizing, or ``OrderCreate``.
8. ``compute_indicators`` + ``select_strategy`` — calculation; allocate() reads live
   ``strategies.active`` (RAM/durable flags).
9. ``volatility_ok``, AI vote, RL gate — mixed (AI/RL have I/O and RAM mutation).
10. ``position_sizing`` / notional / USD-direction / portfolio stop-risk — calc + live book.
11. ``execute_oanda_market_open`` / ``OrderCreate`` — broker mutation.

Pure calculations reused by shadow: ``compute_indicators``, ``volatility_ok``,
session clock helpers (reimplemented with explicit config so live env is not required).

Intentionally **not** reused: live ``strategies`` objects, ``operator_set_*``,
``oanda_exec``, ``execute_trade``, Telegram halt/resume, reconciliation writers.

Track A (``original.py``): quant-stub + hybrid routing + argmax allocation.
RL without a Q snapshot is ``NOT_REPRODUCIBLE``. Never mixed with Track B.

Track B (``engine.py``): Stage C indicator heuristics labelled
``EXPERIMENTAL_HEURISTIC``. Not original-bot decisions.
"""
