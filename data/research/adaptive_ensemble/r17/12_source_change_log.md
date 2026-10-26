# Source change log

Pre-stage `forex_bot/bot_loop.py`: `27934fe441420b0a978bfbb207b2a21a98b9420415668f60b98fc05db4422f4e`.

Post-stage `forex_bot/bot_loop.py`: `683cb8d172011548820b48fd936e583e0be991e7e79adc6f37e97c309005bf4a`.

`app.py`, `database.py`, and `orders.py` were not modified. Protected files, configuration defaults, sizing formulas, and strategy algorithms were not modified.

R.17 changes inside `evaluate_one_instrument_iteration` and its helpers:

- `IterationDependencies` gained `bid`, `ask`, `quote_as_of`, and `unrealised`.
- `_market_entry_block` replaced the previous permissive short-lookback and spread notes.
- `_entry_lookback_requirement` reads the selector lookback or the existing scalp, swing, and default constants.
- `_configured_unit_cap` reads `MAX_POSITION_UNITS` and blocks above an enabled cap before reservation.
- `_pending_gross_usd` adds blocking reservations when the gross percentage is above zero and fails closed when that exposure cannot be read.
- `block_reason` runs only when `account_risk_enabled()` is true, using the accepted equity.
- Margin evidence is recorded as not implemented.

Hash pins in `tests/test_r8_reservation_safety.py`, `tests/test_r10_offline_startup.py`, and `tests/test_r11_historical_recovery.py` now name the post-stage `bot_loop.py` hash.

Tests added: `tests/test_r17_hard_risk_gates.py`.

Fixture updates: default bar count 50 and synthetic bid/ask in the R.12–R.16 helpers. R.12 J16, J17, J19, J20, and J32 now expect the fail-closed results.
