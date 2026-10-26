# R.69 management integration

Function executed: `forex_bot.bot_loop._evaluate_impl` via `asyncio.run`. `run_bot` was not called.

Candles are synthetic and flat around 1.1002. The live quote is an in-memory `ManageQuote` at the same price. Weekend flatten is false on this Sunday because `flatten_for_weekend` is true only on Friday. `execute_trade` and `close_position` on the `bot_loop` module were wrapped to record calls and then use the real delete for `close_position`. `execute_oanda_market_close` raises if reached.

| Resident row | Branch reached | Broker write | Local row |
| --- | --- | --- | --- |
| `observation_only`, kind `reconcile_import` | Return at the ownership guard | None. No quote, no profit protection, no `execute_trade`, no `close_position` | Kept |
| Kind `reconcile_import`, flag false | Same guard return | None | Kept |
| Flag true, kind forged `live` | Same guard return | None | Kept |
| Unknown, empty, `???`, `LIVE-FORGED` | Same guard return | None | Kept |
| `paper`, `simulated`, `window_paper` | Past the guard. Real `apply_profit_protection` runs | None | Kept. Price is inside stop and target, so the close tail is not taken |
| `synthetic` | Same as paper | None | Kept |
| Kind `live`, flag false, client id and trade id set | Quote snapshot and real profit protection | `close_fill_path` is `abort_broker_disabled` in paper mode. `execute_trade` and `PositionClose` are not called | Kept |

The live row was built with the fields the entry tail passes to `open_position`: kind from the fill path, `observation_only` left at the default false. The tail itself was not called. That provenance claim is `NOT_VERIFIED`. The source still contains `status="blocked"` and does not set `observation_only=True` on that constructor.

A test-only predicate that always returns true makes the same observation row reach `apply_profit_protection`. The real predicate does not. The harness can see a removed guard.
