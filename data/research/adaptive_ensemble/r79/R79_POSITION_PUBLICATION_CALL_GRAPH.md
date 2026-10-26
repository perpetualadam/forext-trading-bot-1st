# R.79 Position Publication Call Graph

Evidence class: static search of `forex_bot` plus executed tests for the operational and offline paths.

## Operational writers

| Location | Function | Classification | Fence |
| --- | --- | --- | --- |
| `position_recovery.py` 388–414 | `publish_recovered` | `FENCED_OPERATIONAL_PATH` | Missing epoch or inactive session returns `recovery_authority_absent`. A current session with a mismatched journal epoch returns `recovery_fence_lost`. |
| `position_recovery.py` 417–440 | `_place_recovered_position` | Reached operationally only through `publish_recovered`. Also reached by the offline function below. | The operational caller has already checked the fence. |
| `startup_recovery.py` 323 | caller of `publish_recovered` | `FENCED_OPERATIONAL_PATH` | Runs only after claim, epoch assignment, snapshot acceptance, and the fence check at line 274. |
| `entry_capture.py` 103–134 | `record_entry_response` | `FENCED_OPERATIONAL_PATH` | `commit_verified_entry` commits first. Lines 110–117 skip the memory write when the fence is false and set `publication_reason` without changing `reason`. |
| `startup_recovery.py` 257 | `positions.clear` | `FENCED_OPERATIONAL_PATH` | Clears the book during an in-progress recovery after the lock and epoch claim. It does not publish a broker position. |

`publish_recovered` callers in operational source are the startup loop and the function definition. Research tests also call it. A direct call with no epoch was executed in `test_03` and refused.

## Offline and non-operational writers

| Location | Function | Classification | Reachability |
| --- | --- | --- | --- |
| `position_recovery.py` 443–454 | `recover_managed_book` | `OFFLINE_ONLY_PATH` | Calls `_place_recovered_position` directly. Repository search shows callers in its definition and `r75/poc/test_r75_guard_and_recovery.py` only. Startup, entry capture, and the bot cycle do not call it. `test_04` published through it and `live_management_permitted()` stayed false. |
| `positions.py` 87–106 | `open_position` | `OFFLINE_ONLY_PATH` for paper, synthetic, and backtest callers. | Writes `positions[symbol]`. It does not itself send an order. Broker-backed live opens that reach a write go through `_submit_order_create` first. |
| `positions.py` 313–366 | `import_position_from_broker` | `OFFLINE_ONLY_PATH` | Writes `broker_observations`, forces observation-only, and does not put the row in the managed dict. |
| `positions.py` 113–195 and 286–299 | close, confirmed close, paper displace | Removal paths | Confirmed live removal requires a fully confirmed close identity. Observation-only symbol delete is refused. |
| `orders.py` 344 | synthetic fill recorder | `OFFLINE_ONLY_PATH` | Opens an in-memory synthetic position. The function documents that it does not call a broker. |
| `backtest.py` 528 and 638 | backtest book reset | `OFFLINE_ONLY_PATH` | Clears or restores the process book for a simulation. |
| `shadow/engine.py` 150, 798, 876 | shadow book | `UNREACHABLE_PATH` for the operational book | Those assignments use `self.positions`, not `forex_bot.positions.positions`. |

No background task or callback publisher other than `record_entry_response` was found. Quarantine writes go to `quarantined_positions`, which is not the managed book.

A path is not classified offline because its name contains "recover". `publish_recovered` is operational because startup calls it. `recover_managed_book` is offline because no operational caller references it.
