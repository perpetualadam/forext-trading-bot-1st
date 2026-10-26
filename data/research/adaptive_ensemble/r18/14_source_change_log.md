# Source change log

Pre-stage `forex_bot/bot_loop.py`: `683cb8d172011548820b48fd936e583e0be991e7e79adc6f37e97c309005bf4a`.

Post-stage `forex_bot/bot_loop.py`: `c25ea5dd2c616324bfc43356c9c372358c1374009c2a59ed4149e5ecc458d17e`.

`app.py`, `database.py`, and `orders.py` were not modified. Thresholds, sizing formulas, strategy algorithms, and protected files were not modified.

R.18 additions in `bot_loop.py`:

- `_record_gate` stores one status per gate and keeps an earlier failure.
- `_record_standing_production_gaps` records live permission, numeric spread, margin, and production provenance as non-passes.
- `_seal_entry_gates` and `_synthetic_dispatch_block` run before reservation.
- `_build_risk_decision` attaches `risk_decision` and `production_eligible` to every iteration result.
- `_market_entry_block` now blocks a missing, invalid, or negative quote-time or spread input. The 90-second window is unchanged.

Hash pins in the R.8, R.10, and R.11 tests name the post-stage hash. R.12–R.17 fixtures supply `quote_as_of`. Tests added: `tests/test_r18_entry_eligibility.py`.
