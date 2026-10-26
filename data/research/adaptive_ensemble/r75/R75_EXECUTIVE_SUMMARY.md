# R.75 Executive Summary

Stage: Universal Broker-Write Guard, Durable Position Recovery and End-to-End Concurrency Verification.

Classification: `R75_IMPLEMENTATION_PARTIALLY_VALIDATED`

Production trading remains **NO-GO**.

Retained limitations:

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`
- `LINUX_INTEGRATION_NOT_VERIFIED`
- `REAL_NETWORK_EXECUTION_NOT_TESTED`
- `POSTGRESQL_INTEGRATION_NOT_TESTED`

## What this stage changed

The only operational `PositionClose` constructor, `forex_bot/oanda_exec.py` `_submit_position_close_body` (lines 401–459), now refuses to call the synthetic or real client unless `CloseJournal.claim_network_permit` consumes a matching one-shot permit. `trading.execute_trade` (line 391) raises before any broker call when `execution_kind` is `live`.

Bot-owned position identity can be stored in the same SQLite file as the close journal (`managed_positions`, schema version 2) and restored by `forex_bot/position_recovery.py`. Missing protection fields, an activated ratchet with NULL stop fields, broker-only discoveries, and identity conflicts stay quarantined. Restoration does not grant close authority and does not submit a close.

## What was verified offline

Windows CPython 3.13 ran `data/research/adaptive_ensemble/r75/poc/test_r75_guard_and_recovery.py`: 13 tests passed. Two independent processes executed `run_guarded_live_close` against one temporary journal and one shared SQLite `PositionClose` recorder. Exactly one recorder row was written. A third process after reopen did not add a second row. A process paused inside the synthetic request, after the journal claim, blocked the other process from recording a close.

R.74 journal tests: 20 passed on Windows and 20 passed on WSL CPython 3.12.3. R.74 operational recovery tests: 9 passed on Windows. The WSL operational import stops at `forex_bot/oanda_client.py` line 13 with `ModuleNotFoundError: oandapyV20`.

## What is not claimed

A SQLite claim and the later OANDA HTTP request are not one atomic transaction. This stage does not claim exactly-once broker execution. Power loss during fsync was not tested. The production loop in `bot_loop.py` does not yet call `recover_managed_book` before management. Entry still does not record a broker trade id, so a restart before `persist_bot_position` has no durable row to restore. No real broker call was made.

R.76 was not started.
