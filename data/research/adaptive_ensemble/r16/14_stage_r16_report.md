# STAGE R.16 — OFFLINE ACCOUNT-RISK CONSISTENCY AND EQUITY-SOURCE UNIFICATION REPORT

Classification: `R16_OFFLINE_EQUITY_SOURCES_UNIFIED`.

`forex_bot/bot_loop.py` is the only application module modified. R.16 tests: 141 collected, 135 passed, 0 failed, 6 skipped (H136–H141 NOT_EVALUATED). Sizing and the portfolio cap use the same accepted equity. The shared entry path does not call `current_equity()`. Fallback equity cannot authorise an entry. The selector, vote wrapper, and RL veto ran. Inert BUY and SELL each recorded one adapter request. The production adapter was not invoked. `run_bot` and the launcher did not run. Real broker requests, network successes, and PostgreSQL connections are 0.

Production account provenance is NOT_EVALUATED. Broker execution is SOURCE-VERIFIED and not invoked. PostgreSQL is NOT_EVALUATED.

STOP. R.17 is not started.
