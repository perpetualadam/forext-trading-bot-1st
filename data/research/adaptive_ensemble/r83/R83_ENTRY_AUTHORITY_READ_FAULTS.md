# R.83 entry authority-read faults

Executed against `_submit_order_create` or `_place_market_order_open_sync` after a real startup.

| Test | Fault | OrderCreate | Permit |
| --- | --- | --- | --- |
| `test_11` | Injected `OperationalError("database is locked")` on the third authority call. Label `INJECTED_SQLITE_BUSY` | 0 | Claimed before the failing call. Classified as an ambiguous transport outcome and not retried |
| `test_11` | Injected `OperationalError("database table is locked")` on a second entry, client `client-locked`. Label `INJECTED_SQLITE_LOCKED` | 0 | Same fail-closed path. No OrderCreate |
| `test_12` | Closed SQLite connection | 0 | The claim has not been verified while the connection is closed. The exception happens before `api.request` |
| `test_12` | Authority row deleted | 0 | `EntryGuardRefusal` before a new claim completes for `client-missing` |
| `test_09` | Genuine `SQLITE_BUSY` on a DELETE-mode SELECT | 0 | Not the production sink. No order is built |

No second entry is submitted after these faults. `test_02` shows the consumed client cannot be reserved again once finalised.
