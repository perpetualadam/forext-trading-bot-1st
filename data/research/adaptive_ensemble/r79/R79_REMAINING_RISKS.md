# R.79 Remaining Risks

These limitations stay open. Offline synthetic tests do not clear them.

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`. OANDA documentation does not establish that a repeated client id is rejected by the broker.
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`. WAL and `synchronous=FULL` remain configured. No power-cut test was run.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`.
- `POSTGRESQL_INTEGRATION_NOT_TESTED`.
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`.
- The check inside the write adapter does not bind the fencing epoch to the HTTP request. A repair or crash between the check and `api.request` can still race the socket.
- Several phase-M rows were not separate one-cycle cases: multiple managed trades, ambiguous entry at startup, conflicting account binding, profit-protection evaluation on a live row, and journal corruption after a successful startup.
- No broker TradeCRCDO or protection-replace sink exists. Local stop ratchets are not broker-side modifications.
- Windows boot identity is a constant, so reboot detection on Windows is not verified.
- `requirements.txt` is not hash-pinned. This install is recorded. A later install can resolve different wheels.
- R.66 findings that remain outside this stage: `broker_sl_tp_hit` always false in `live_manage.py` (R66-03), sizing currency (R66-07), journal-side duplicate close suppression rather than broker enforcement (R66-10 and R66-11), and R66-16.

Production trading remains NO-GO.
