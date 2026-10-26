# R.80 recovered multi-trade cycle

Evidence class: executed operational cycle. `test_14` and `test_15` call `run_startup_and_one_iteration`, which calls the real `_execute_bot_cycle`. The test wraps that function only to count calls. It does not replace the cycle body.

Disposable journal rows:

- EUR_USD BUY, GBP_USD SELL, USD_JPY BUY.
- Distinct synthetic trade ids, matching account binding, instrument, and position instance.
- Stop-loss and take-profit present.

Snapshot additions that are not durable managed rows:

- AUD_USD broker-only.
- NZD_USD manual.

Results from the Windows and Linux runs:

- `cycle_calls == 1` and `last_bot_cycle_utc` is set. The real cycle ran.
- Startup state is `RECOVERY_COMPLETED_WITH_QUARANTINE` because the extra snapshot rows and the synthetic account-summary body are not a clean managed book.
- `positions` contains exactly EUR_USD, GBP_USD, and USD_JPY. No duplicate and no silent drop of those three.
- AUD_USD and NZD_USD are not in `positions`.
- `test_15` overrides the GBP account binding in the snapshot. GBP is quarantined. EUR and JPY remain.
- The cycle's synthetic write list is empty. Account-summary and candle reads are logged as invalid or missing. Those are reads.
- The cycle log `broker protection evidence withheld: malformed_body` is the existing protection read against the synthetic body. No protection order was sent.

`R80_MULTIPLE_MANAGED_TRADES_RECOVERED`: PASS.
