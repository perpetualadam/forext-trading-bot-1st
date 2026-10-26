# Offline initialization execution

Status: REAL INITIALIZATION EXECUTED WITH FAKE DEPENDENCIES. This is not production startup.

`test_i01_offline_initialization_succeeds` calls `initialise_application`, reaches `offline_initialization_ready`, then calls `shutdown_application`.

Observed success state:

- `ok` true
- `offline_ready` true
- `trading_ready` false
- `trading_loop_started` false
- phase list ends at `offline_initialization_ready` and does not contain `running`
- effective live-order auth is `BLOCKED`
- strategy objects stay inactive
- `forex_bot.oanda_client` and `oandapyV20` were absent when that assertion ran
- `database._pg_conn` stayed `None`
- the scheduler result was `recorded_not_started`
- `run_bot` was not imported by the offline seam

The production lifespan and `_production_startup_ports` were not called. I66 records that production startup as NOT_EVALUATED.
