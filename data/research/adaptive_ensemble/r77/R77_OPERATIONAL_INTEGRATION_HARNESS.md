# R.77 operational integration harness

`data/research/adaptive_ensemble/r77/poc/test_r77_atomic_entry.py` imports the R.69 isolation harness before any `forex_bot` module. It then calls `bot_loop.run_startup_and_one_iteration` with a synthetic broker view and a `RecordingAPI`. Write endpoint names raise `IsolationBreach`. Read endpoint failures are contained by the existing account, pricing, and candle handlers.

The harness does not construct a second management implementation. `_execute_bot_cycle` is the same function `run_bot` calls. Tests 66 and 67 observed:

- the startup report reached `RECOVERY_COMPLETED` before the assertion on `live_management_permitted`
- the recovered `EUR_USD` position was present
- `OrderCreate` and `PositionClose` counts were 0

The cycle logged `InstrumentsCandles`, `AccountSummary`, and `PricingInfo` isolation breaches and `decision_candles_missing`. Those are contained read failures, not broker writes. With no fresh quote, management recorded `broker protection evidence withheld: request_exception` and did not submit a close.

Test-only exposure patching exists in test 25 so one synthetic `OrderCreate` can reach the capture fault. The default `assert_new_live_exposure_allowed(action="open")` still raises. That patch is restored in `tearDown`.

`production_execution_adapter_withheld` remains the non-simulation result (`bot_loop.py` lines 4290–4301). `production_adapter_refusal` still returns `production_ineligible` when `production_eligible` is not true (test 81). An entry permit passed to `_submit_position_close_body` raises `CloseGuardRefusal` before a request (test 78). A close permit passed to `_submit_order_create` raises `EntryGuardRefusal` (test 79). `execute_trade(..., execution_kind="live")` raises before HTTP (test 80).

No PostgreSQL connect attempt was present in `isolation.ATTEMPTS` after the suite (test 86). The temporary journal path was the only `CLOSE_JOURNAL_PATH` (test 90).
