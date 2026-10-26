# Implementation roadmap

No stage below is started. Each one needs its own approval.

## R.7 — Offline PostgreSQL proof

Purpose: run the unresolved-order statements and the reservation lock on a disposable database.

Likely files: tests only, unless the SQL is wrong. Application edits only if the engine test fails.

Stop if the only available database is production, Docker, or a network server.

## R.8 — Fake startup harness

Purpose: prove the process can pass safety load and order recovery without a broker, Telegram, or the real trading loop.

Likely files: `forex_bot/app.py` only if a seam is required, plus a new harness under tests. Live permission stays blocked. Strategies stay inactive.

Stop if the harness opens a socket or starts `run_bot`.

## R.9 — Backtest direction repair

Purpose: remove the BUY fallback in `backtest.py` lines 352–354.

Stop if the change touches live sizing or strategy rules.

## R.10 — Strategy truth

Purpose: decide whether the six names stay labels. Do not connect shadow rules to orders in that stage.

## Later, still separate

Risk-flag review, more local sessions without a download unless approved, then a practice-account review, then a production review. Practice and production stay unauthorised until those explicit approvals.

Do not skip R.7 or R.8 to work on strategies or profit.
