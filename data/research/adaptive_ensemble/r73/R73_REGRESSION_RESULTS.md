# R.73 Regression Results

Windows CPython 3.13.5. Historical test files were not edited.

| Suite | Result | Meaning |
| --- | --- | --- |
| R.71 calculations | 8 passed | Profit-protection arithmetic still matches |
| R.72 protection | 36 passed, 1 failed | Behavioural protection tests passed. The failure is the historical hash pin for `positions.py` |
| R.70 snapshots | 25 passed, 1 failed | Classification, stale publication, and incomplete refusal passed. `test_valid_then_incomplete_then_valid_empty_sequence` still expects the live row to disappear |
| R.68 ownership | 28 passed, 2 failed, 1 skipped | `test_15_bot_created_row_stays_manageable` calls `close_position` on a live row with no close evidence. That delete is now refused. `test_17` still pins the pre-R.72 `live_manage.py` prefix. R.73 did not edit `live_manage.py` |
| R.69 integration | 46 passed, 2 failed, 1 skipped | `test_operational_hashes_match_r68` stops on the new `positions.py` hash. `test_permitted_live_flat_snapshot_still_drops_local_row` expects the old deletion. The manage path still reached protection evidence and did not call `execute_trade` |

These five failures are historical assertions of the old delete path or of pre-R.73 hashes. They are not profit-protection, ownership-promotion, or snapshot-classification regressions.

`R73_OBSERVATION_AUTHORITY_UNCHANGED`

`R73_R72_PROTECTION_EVIDENCE_PRESERVED`

`R73_R70_SNAPSHOT_CONTRACT_PRESERVED`
