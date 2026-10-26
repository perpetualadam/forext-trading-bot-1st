# Offline-store selection boundary

Before this stage, `offline_exec_order_store_path` returned whatever path `EXEC_ORDER_OFFLINE_STORE` contained. Insert, update, unresolved persistence, and recovery all preferred that path before PostgreSQL. A stale inherited variable could therefore redirect persistence to JSON.

The selection function now returns only `_OFFLINE_STORE_ARMED`. The environment variable is not read. Production code does not call `arm_offline_exec_order_store`. `main.py`, `forex_bot/app.py`, and `forex_bot/oanda_exec.py` do not contain that name.

Arming requires the context `isolated_offline_test`. A caller-supplied `production_eligible` value is ignored. A refused context or a path outside `data/research/adaptive_ensemble/r22` and `data/research/adaptive_ensemble/r23` disarms the store, fail-closes recovery, and raises `OrderRecoveryUnreadable`. A resolved `..` path that leaves both roots is refused. No file is created for a refused path.

A missing, corrupt, truncated, unreadable, duplicate, or inconsistent store fail-closes on read. A write failure returns false and fail-closes before dispatch. The JSON document is a synthetic order record. It does not set `production_eligible`, and the observed process results kept that flag false.

The production application was not started. The production-path claim is the selection function plus the absence of an arm call in the production sources.
