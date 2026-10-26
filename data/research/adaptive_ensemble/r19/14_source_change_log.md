# Source change log

Application source modified: `forex_bot/bot_loop.py`.

Post-stage SHA-256: `9b6327045e29adc48f37ed81d13db44e216e24e71326284dc6c80079e2e74550`.

Pre-stage SHA-256: `c25ea5dd2c616324bfc43356c9c372358c1374009c2a59ed4149e5ecc458d17e`.

Changes:

- `_build_risk_decision` accepts `units` and `client_order_id` and stores `order_binding`, `gates`, and `seal_id`.
- The producer registers a JSON copy of that decision. The copy is not production-eligible.
- `production_adapter_refusal` rejects missing, forged, synthetic, mismatched, stale, reused, and unauthorised decisions.
- `production_execution_adapter` accepts an optional `risk_decision` and `reservation_id`, refuses before importing the broker module, and still contains exactly one `execute_oanda_market_open` call. That call is unreachable.
- Broker argument names and the live-permission default are unchanged.
- `orders.py`, `database.py`, and `app.py` were not modified.

Tests:

- Added `tests/test_r19_adapter_boundary.py`.
- `tests/test_r18_entry_eligibility.py` K018 now requires stable eligibility fields and a unique generated client-order id.
- Hash pins in the R.8, R.10, and R.11 tests now match the post-stage `bot_loop.py` hash.

Protected files were read for mapping and were not modified. Their hashes match the stage baseline.
