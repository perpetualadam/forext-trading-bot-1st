# R.82 journal submission boundary

## Source order

Both sinks live in `forex_bot/oanda_exec.py`. Close: `_submit_position_close_body`. Entry: `_submit_order_create`.

1. The permit object type is checked.
2. `live_management_permitted()` runs before the permit is claimed.
3. The one-shot permit is claimed (`claim_network_permit` or `claim_entry_permit`).
4. The R.80 check runs again immediately before `acquire_oanda_rest_slot()`.
5. The rate-limit slot is acquired.
6. The R.81 check runs again immediately after the slot.
7. `api.request` runs only after that check returns true.

`live_management_permitted()` in `startup_recovery.py` returns false when recovery is not complete or the process epoch is missing. `_authority_matches()` reads `recovery_authority.fencing_epoch`. It catches only `JournalUnavailable`. A missing row or a different epoch returns false. `sqlite3.ProgrammingError` and `sqlite3.OperationalError` are not converted to false; they propagate from the check, which is still before `api.request`.

## What each journal condition does

| Condition | Source result | Executed |
| --- | --- | --- |
| Authority row deleted | Check returns false. Guard refusal. No request. | `test_02`, `test_03`, `test_04`, `test_05`, `test_08`, `test_09` |
| Connection closed | `ProgrammingError` before `api.request`. No request. | `test_06`, `test_07` |
| Malformed file after the connection is closed and sidecars removed | `open_journal` raises `JournalUnavailable`. Check returns false. | `test_19` observed `live_management_permitted()` false and `JournalUnavailable` on the next entry reservation |
| Missing journal file | `JournalUnavailable("missing_journal")`, check returns false | Source. Not a separate R.82 row |
| `BEGIN EXCLUSIVE` on a second connection | The open WAL connection, and a reopened connection, still read the epoch. The check stayed true. | `test_19` |
| `SQLITE_BUSY` / `SQLITE_LOCKED` | Not produced by the exclusive-lock attempt. Propagation would be fail-closed if raised before `api.request`, but that path was not executed. | `NOT_VERIFIED` |
| Stale process epoch | Check compares the stored epoch with process memory and returns false | Source, preserved from R.81. R.82 race uses a real successor startup rather than a forged epoch |
| Unwritable but readable journal (`before_commit`) | The epoch SELECT still succeeds, so the request can be entered. The next commit then fails. | `test_12`, `test_13` |

A successful earlier check does not keep the later check from reading the journal again. The later check is still not atomic with `api.request`.
