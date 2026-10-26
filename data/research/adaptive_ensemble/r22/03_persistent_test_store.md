# Isolated persistent test store

`EXEC_ORDER_OFFLINE_STORE` points at one JSON file under `data/research/adaptive_ensemble/r22/stores/`. When the variable is unset, order persistence is unchanged and PostgreSQL settings are unchanged.

The file schema is `exec_orders_offline_v1`. The application writes it from `insert_exec_order_pending_if_absent`, `update_exec_order_row`, and `persist_unresolved_order`. Those functions do not call `get_connection` while the store path is set. A write uses a temporary file and `os.replace`. A write failure fail-closes the reservation and does not dispatch.

`read_offline_exec_orders` is only the storage boundary. A missing file, corrupt JSON, a truncated row, a missing client id, a duplicate client id, or a reservation status that disagrees with the order status raises `OrderRecoveryUnreadable` and fail-closes. An existing file with an empty order list is readable and holds nothing. That empty file is not treated as proof that a missing file is clear.

This store is not PostgreSQL and is not evidence of production durability.
