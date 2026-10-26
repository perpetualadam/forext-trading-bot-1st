# R.71 Trailing Stop and Profit Protection

Classification of the local layer: implemented and connected to management. Classification of a broker trailing stop: missing.

The module states that it is an extra close layer and does not move broker or local stop or take-profit (`profit_protection.py` line 1).

## Activation

`profit_protection_trigger_percent` defaults to 0.67 (`profit_protection.py` 36–38). `activation_trigger_pips` multiplies that by `original_tp_distance_pips` (315–323). The distance uses the position's stored `take_profit` and `entry_price` (283–312). No operational assignment to `position.take_profit` was found after construction, so the trigger uses the original stored target rather than a later rewritten one.

BUY requires the target above entry. SELL requires it below. A wrong-side target disables protection (`mfe_meets_activation` returns false).

The isolated test used a 30-pip target and observed a 20.1-pip trigger on both sides.

The price that updates MFE is the management price. For a broker-backed row that is the closeout bid for BUY and the closeout ask for SELL (`live_manage.py` 33–45). For paper it is the candle close (`bot_loop.py` 831–833). Spread is inside the closeout quote. It is not added again. MFE can also be seeded from candle high and low (`seed_position_mfe`), so the extreme can be wider than the executable closeout.

Activation state is the in-memory flag `profit_protection_active`. It is not written to a database.

The percent is an environment default, not a comment-only constant. The test read the function, not a comment.

## ATR giveback

Period default 14 (45–49). Multiplier default 0.5 (41–42). `latest_atr_price` is a simple moving average of true range (`indicators.py` 8–18 and 97). It is not Wilder's smoothing. The last row of the frame is included. This function does not drop an incomplete candle. `fetch_ohlcv_range` documents that it skips incomplete candles (oanda_client.py 335). The manage path's frame is whatever `_load_decision_candles` returns. This audit did not execute that loader. Whether a forming bar is in the live frame is `NOT_VERIFIED`.

ATR is converted from price to pips by dividing by pip size (201–211). A 0.0010 EUR_USD ATR became 10 pips and a 0.5 multiplier became 5 pips in the test. Giveback is clamped between 0.5 and 30 pips by default (57–62, 243–253).

Missing or non-positive ATR uses the 4-pip fallback and logs it (230–241). It does not disable protection.

## Pip size

Quote currency JPY uses 0.01. Other canonical names use 0.0001 (`profit_protection.py` 73–80). The test confirmed EUR_USD and USD_JPY.

## Ratchet

`update_protected_exit_pips` stores `max(previous, MFE - giveback)` (265–280). A larger ATR giveback in the test did not lower the stored threshold. MFE itself only increases (650–655).

Restart drops the object because positions are process memory. Imported observations do not reach this function: the ownership guard returns first (`bot_loop.py` 795–802). The R.71 test confirmed `position_management_permitted` is false for an observation.

## Close

When `should_close` is true, `_evaluate_impl` calls `execute_trade` and then `close_position` (1071–1098). Paper and window-paper paths are local. A `live` kind calls `execute_oanda_market_close` only when broker orders are enabled, and otherwise raises so the local row is kept (`trading.py` 391–398). The broker request is `PositionClose` for the whole unit size (`oanda_exec.py` 418–424). The manage path then deletes the local row if that call returns. It does not compare closed units with requested units. This is not a broker trailing stop.

`protection_close_allowed` defers a repeat for 30 seconds after an attempt (734–742). That cooldown is not an idempotency key.
