# Remaining blockers

1. Historical FILLED rows without `metadata.exposure_safety = UNCONFIRMED` are still absent from `fetch_exec_orders_open_for_recovery`. The gap is not resolved. A row handed directly to ingest is blocked. The durable fetch used by production recovery does not return that row.
2. PostgreSQL was not started and no recovery SQL was executed. I64 is NOT_EVALUATED.
3. Broker reconciliation and broker position state were not contacted. I65 and I67 are NOT_EVALUATED.
4. `lifespan` and `_production_startup_ports` were not executed. I66 is NOT_EVALUATED.
5. `run_bot` was not executed. I68 is NOT_EVALUATED.
6. Positions remain in-memory. Shutdown of the offline seam does not create a durable position record.
7. `confirm_exposure_flat` still does not clear a durable UNCONFIRMED marker. That marker was not rewritten by this stage.

No integration step required an unapproved file. `main.py`, `oanda_exec.py`, `live_safety.py`, `strategy_meta.py`, `telegram_control.py`, `config.py`, and the Docker files were not modified.
