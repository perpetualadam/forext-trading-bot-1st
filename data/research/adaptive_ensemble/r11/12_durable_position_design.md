# Durable position recovery design

This is a design only. No table and no migration were added.

J01. Positions live in `forex_bot/positions.py` as one in-memory slot per symbol. There is no open-position table.

J02. A slot stores symbol, direction, units, entry price, stops, open time, strategy name, client and broker ids, and local protection fields. It is not recovered from PostgreSQL.

J03. `exec_orders` stores client id, symbol, side, units, status, timestamps, fill price, broker order id, and JSONB metadata. `exposure_safety` is a metadata key, not a column.

J04. Missing durable fields: open units still at the broker, close transaction id, close price, close time, broker position id, and an authoritative flat timestamp.

J05. A fill would append an order row and, only after a confirmed broker position snapshot, upsert one position row. The order status alone would not create that row.

J06. Partial fills would accumulate `filled_units` on the order and leave the position row at the broker-reported units. A partial row would stay blocking until the position snapshot matches or an explicit close is stored.

J07. A close would insert a close event keyed by the broker transaction id. The position row would be marked closed only from that event or from a broker snapshot that shows zero units.

J08. Authoritative reconciliation would read the broker position and open trades, compare them with the local position row, and write the comparison time. It would not run inside this stage.

J09. A snapshot older than the latest order event, or a snapshot whose units disagree with the summed open fills, is stale. Stale data fail-closes.

J10. Startup would load uncertain orders and the position row. Any disagreement, missing snapshot, or unread query would block new entries.

J11. A position table is required if positions must survive a restart. The order table cannot represent an open position by itself.

J12. A migration is required before that table can exist. This stage does not authorise one.

J13. Historical FILLED rows without a flat marker stay blocking. They are not rewritten into positions and they are not declared closed.

J14. The hold ends when a later authorised reconciliation stores broker-flat evidence, or when an operator accepts a reviewed position migration. It does not end on a timer, and `CONFIRMED_FLAT` in metadata is not that evidence.

J15. Fresh authorisation is required for the migration, for applying it, for starting PostgreSQL, and for any broker position read.
