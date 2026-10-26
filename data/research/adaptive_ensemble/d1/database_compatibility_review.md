# Database compatibility review

Classification: `DATABASE_COMPATIBILITY_UNVERIFIED`.

The live database was not queried. The container `forexttradingbot1st-db-1`, image `postgres:16-alpine`, and volume `forexttradingbot1st_pgdata` are historical names only.

## Source

`forex_bot/database.py` matches the G.10 allowlist and the G.12 image sample (`98ed215c0a7e7f21ecf938172a45805a3f1b456c5cf49e8d0a8ea9f0d5cbce72`). There is no separate migration package.

On first `get_connection`, the source executes and commits:

- `CREATE TABLE IF NOT EXISTS` for `trades`, `reconcile_metadata`, `operational_event_log`, `exec_orders`, `broker_exit_ledger`, and `broker_exit_pending`
- `ALTER TABLE trades ADD COLUMN IF NOT EXISTS` for `trading_mode`, `execution_kind`, and `diagnostics`
- `ALTER TABLE exec_orders ADD COLUMN IF NOT EXISTS filled_units`
- `CREATE INDEX IF NOT EXISTS` on the operational event log and exec orders

No `DROP`, `TRUNCATE`, or column rewrite was found in that function.

## Compatibility

Backward: additive `IF NOT EXISTS` statements are the usual way to leave an older database readable by this same source. Whether the live database already has these tables is unknown. A failure to connect is logged and startup continues without a connection. Later order and reconcile calls then have no database.

Forward: this source does not understand a table change that a future release might require. Extra columns already present are not dropped by these statements.

Downgrade: columns added by this source remain if an older image starts afterward. If the older image does not select those columns, PostgreSQL usually ignores them. If the older image expects a different type, that was not proven. The sampled image has the same `database.py`, so a rollback to that image does not remove this DDL.

Irreversible change in this DDL: none identified. Irreversible change from application writes during startup and reconciliation: possible, and not measured.

## Still required

An offline fixture of the current schema, a run of this DDL against a copy, and a check that application queries still match that copy. None of that is evidence today. G.13 reached the same unverified classification and the source bytes have not changed.
