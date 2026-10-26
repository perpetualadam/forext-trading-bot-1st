# Database schema requirements

Classification: `SOURCE_SCHEMA_REQUIREMENTS_DOCUMENTED`, `LIVE_SCHEMA_UNVERIFIED`, `SCHEMA_COMPATIBILITY_BLOCKED`.

`forex_bot/database.py` lines 25–112 declare:

- `trades`, including later additive columns `trading_mode`, `execution_kind`, and `diagnostics`
- `reconcile_metadata`
- `operational_event_log` and `idx_operational_event_log_id_desc`
- `exec_orders`, its two indexes, and additive column `filled_units`
- `broker_exit_ledger`
- `broker_exit_pending`

The statements are `CREATE TABLE IF NOT EXISTS` and `ADD COLUMN IF NOT EXISTS`. No schema-version table is declared. `get_connection()` runs these statements while holding `_pg_lock`, then publishes one connection and one cursor.

No migration tool, no live catalog, and no production connection were used. The live schema version is not invented here. Startup against a production database remains blocked until a disposable comparison and a separate live inspection exist.
