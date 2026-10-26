# Database schema audit

SOURCE-REVIEWED. No SQL was sent to a server.

`exec_orders` is created by `CREATE_EXEC_ORDERS_SQL` in `forex_bot/database.py` lines 72–88.

- `client_order_id` is `TEXT UNIQUE NOT NULL`.
- `status` is `TEXT NOT NULL`.
- There is no check constraint on the status word.
- There is no unique rule that one symbol can have only one open row.
- Indexes exist on status and created time.
- `filled_units` is added with `ALTER TABLE ... IF NOT EXISTS` when a connection is first opened.
- `UNRESOLVED` is a Python status string. It fits the text column. It is not a separate schema object.
- Pending, partial, filled, and cancelled are also plain text. Rejected is used in the in-memory book, not as a required database word. Confirmed rejection in the live path is stored through the cancel update.

No migration was written or run. A later engine test would be the place to decide whether a partial unique index on open statuses is required. That change must not be applied to an existing database in this stage.
