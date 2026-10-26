# Dependency injection design

`initialise_application` in `forex_bot/app.py` is the orchestration boundary. `StartupPorts` carries the callers. Production lifespan builds `_production_startup_ports`. Tests build `OfflineServices.ports()` with `mode="offline"`.

Offline mode accepts only the scheduler result `recorded_not_started`. Any other result raises `StartupSafetyAbort`. `trading_ready` is set false on both the success and failure paths. `offline_ready` becomes true only after the offline phase list reaches `offline_initialization_ready`.

The phase order is:

1. created
2. configuration_validated
3. safety_defaults_verified
4. persistence_initialized
5. order_recovery_completed
6. exposure_safety_evaluated
7. broker_dependency_initialized
8. market_data_dependency_initialized
9. messaging_dependency_initialized
10. health_dependencies_prepared
11. offline_initialization_ready, or `running` for the production mode

Recovery uses three explicit inputs:

- `_PRODUCTION_RECOVERY` calls the production recovery port. Tests do not use it.
- `_CALL_RECOVERY` calls the injected provider and then the real `ingest_recovery_snapshot`.
- Any other value is passed straight to `ingest_recovery_snapshot`.

Exposure uses the real `exposure_entry_block_reason` for the injected symbol list. `ReconciliationUnavailable` is recorded and does not clear those holds. Every other dependency exception fail-closes, closes what the offline path already opened, and does not mark ready.

`shutdown_application` closes scheduler, health, messaging, market data, broker, and persistence in that order. A second call is safe. Shutdown does not start the application again.

A lifecycle dictionary refuses a second successful initialization and refuses initialization after shutdown unless the test sets `allow_repeat` or `allow_after_shutdown`.

Production defaults stay fail-closed. The production scheduler still creates the `run_bot` task, and only when lifespan runs. The offline tests never request that port.
