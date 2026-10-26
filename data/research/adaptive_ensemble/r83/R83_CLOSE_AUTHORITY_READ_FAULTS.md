# R.83 close authority-read faults

| Test | Fault | PositionClose | Confirmation |
| --- | --- | --- | --- |
| `test_11` | Injected `OperationalError("database table is locked")` on the EUR_USD close. Label `INJECTED_SQLITE_LOCKED` | 0 | Not `CLOSE_FULLY_CONFIRMED`. `network_permit=1` |
| `test_11` | Injected `OperationalError("database is locked")` on a separate GBP_USD trade `T2`. Label `INJECTED_SQLITE_BUSY` | 0 | Not `CLOSE_FULLY_CONFIRMED`. `network_permit=1` |
| `test_14` | Epoch incremented by another connection | 0 | Not fully confirmed |
| `test_14` | Closed connection before `run_guarded_live_close` | 0 | The call raises. No close is confirmed |
| `test_10` | `SQLITE_LOCKED_SHAREDCACHE` on shared-cache `BEGIN IMMEDIATE` | 0 | Not the production close sink |

A failed authority read does not finalise a close and does not release a consumed permit. The durable permit for the injected post-claim failure is read after the connection is still open, so that permit state is verified. The closed-connection case is not described as a verified permit value, because the connection cannot be read until it is reopened and this test stops at the raised exception and the zero write count.
