# R.71 Stop, Take-Profit, and Breakeven

These six things are separate. The source implements some of them and not others.

| Kind | Status | Evidence |
| --- | --- | --- |
| Local stop distance calculation | Implemented, call site blocked | `sl_tp_price_distances` and `sl_tp_distance_for_entry`, `trading.py` 82–134 |
| Stop price stored in RAM | Implemented when a position is opened | `Position.stop_loss`, `positions.py` 18 |
| Stop attached to an OANDA order | Implemented in the open helper, entry path blocked | `stopLossOnFill`, `oanda_exec.py` 477–501 |
| Confirmed broker-side stop | Not implemented | `broker_sl_tp_hit` returns false, `live_manage.py` 76–78 |
| Dynamically amended broker stop | Missing | Profit protection does not send a stop amendment |
| Local software-triggered close | Implemented for permitted rows | `bot_loop.py` 890–894 and 1071–1098 |

## Initial distances

`USE_ATR_STOPS` defaults false. The fallback is 20 pips times pip size, and the target is twice that (`trading.py` 82–98). The isolated test observed 0.0020 and 0.0040 on EUR_USD, and 0.20 and 0.40 on USD_JPY. If ATR stops are enabled, distance is `SL_ATR_MULT` (default 2) times ATR, with an optional price floor (119–134). The call is at `bot_loop.py` 1439, after the entry block at 1139.

Paper management compares the candle price with the stored stop and target (890–894). Broker-backed management does not. It asks `broker_sl_tp_hit`, which returns false, so a broker stop fill is not detected by this function. R66-03 remains open. A stored local price is not a confirmed broker stop. R66-05 remains open.

## Breakeven

No operational function moves a stop to entry or applies a breakeven buffer. A research lifecycle field named `break_event` is a candle-structure record, not a trade stop (`forex_bot/research/learning/lifecycle.py`). Automatic breakeven is `MISSING`. It was not marked complete.

## Rounding and restart

Opening orders format a price for OANDA inside `_format_oanda_price` when the blocked open helper runs. This audit did not execute that formatter. Restart does not reload `Position.stop_loss` from the broker. There is no position table.
