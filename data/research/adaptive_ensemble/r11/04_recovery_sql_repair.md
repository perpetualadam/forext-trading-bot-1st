# Recovery SQL repair

CODE MODIFIED in `forex_bot/database.py`. The SQL text was captured from a fake cursor. PostgreSQL did not execute it.

`RECOVERY_SELECTION_SQL` (lines 495–498):

```text
status IN ('PENDING', 'PARTIAL', 'UNRESOLVED')
OR (status = 'FILLED' AND COALESCE(metadata->>'exposure_safety', '') <> 'CONFIRMED_FLAT')
```

`fetch_exec_orders_open_for_recovery` (line 1062) and `read_durable_recovery` (line 848) both use that text. The fetch limit is 2001. More than 2000 rows raises `OrderRecoveryUnreadable` so a partial page is not treated as a complete book.

`RESERVATION_BLOCK_SQL` (lines 499–502) blocks a new reservation unless the existing row is CANCELLED, REJECTED, or FILLED with exactly `CONFIRMED_FLAT`. The symbol remains a bound parameter. The status text is a constant.

NULL and a missing JSON key become `''` under `COALESCE`. That value is not equal to `CONFIRMED_FLAT`, so those FILLED rows stay eligible. Malformed JSON values are not coerced to an empty object during decoding. Ingest rejects a non-object metadata value.

No schema statement was added or applied.
