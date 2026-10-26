# Fake service contracts

Module: `tests/r10_fakes.py`, class `OfflineServices`.

| Fake | Real dependency it stands in for | Contract |
| --- | --- | --- |
| persistence | `get_connection` | Records the call. No URL, no `psycopg2.connect`, no schema, no operational write. |
| recovery provider | `load_open_orders_from_db_into_memory` | Returns injected rows or raises. The real `ingest_recovery_snapshot` consumes them. |
| broker | `build_api` | Records initialization. `submit_order` and `close_position` raise. No OANDA client. |
| market data | account summary and `run_reconciliation_once` | Returns a synthetic read-only snapshot. Can raise `ReconciliationUnavailable` or a generic failure. |
| messaging | startup alert path | Records initialization. `send_message` stores the text locally and raises. No Telegram or Discord call. |
| health | pre-trade warning path | Records initialization or raises. |
| scheduler | `schedule_trading` | Records the attempt and returns `recorded_not_started`. It does not import or call `run_bot`. A refusal raises before a task exists. |

Cleanup records the close order and can return a visible error string or raise. Closed fakes stay closed on a repeated shutdown call.
