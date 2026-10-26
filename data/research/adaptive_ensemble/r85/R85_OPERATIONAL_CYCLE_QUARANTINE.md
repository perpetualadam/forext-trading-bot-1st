# R.85 Operational Cycle Quarantine

Evidence: executed `_execute_bot_cycle` after `execute_startup_sequence`. The helper under test was not a substitute cycle. `run_bot` was not called.

Setup: disposable journal, synthetic broker, partial close of 400 from 1000, ratchet 40, permit consumed.

## Consistent snapshot

Startup with units 600 returned `units_mismatch` and `manageable` false. The cycle then ran.

- The bot log contained `quarantined exposure`.
- `OrderCreate` was absent.
- `PositionClose` remained the original one call.
- The ratchet stayed 40.
- `network_permit` stayed 1.
- No second position was published into `positions`.

Candle loading logged `decision_candles_missing` because the synthetic candle payload was empty. The quarantine return is before the no-candle entry skip. The captured log line shows the quarantine return ran.

`AccountSummary` logged `broker_account_mismatch` for the synthetic summary. That read was not an order.

## Conflicting snapshot

A second startup with units 1000 returned `outstanding_CLOSE_PARTIALLY_CONFIRMED`. A second `_execute_bot_cycle` again recorded no `OrderCreate` and no extra `PositionClose`.

The cycle does not prove a live session would reach an order if the guard were absent. It proves this cycle, with the guard present, did not submit one.
