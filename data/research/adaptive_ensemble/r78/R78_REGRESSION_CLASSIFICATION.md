# R.78 regression classification

Historical files were not edited.

| Suite | Failure | Classification |
| --- | --- | --- |
| R.77 `test_28` | expects `SCHEMA_VERSION == 4` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.77 migration test and R.77 journal migration test | version 4 no longer opens after the 3-to-4 migrator | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.76 `test_28`, `test_35`, `test_36` | pre-R.77 publication and crash expectations | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.73 close evidence | `CLOSE_NOT_REQUESTED` or `missing_journal` where the old test expected a close result | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.72 `test_operational_source_wiring_and_unchanged_files` | `positions.py` hash is the current `ac33eca3...`, not the R.72 pin | `HISTORICAL_HASH_PIN` |
| R.70 `test_valid_then_incomplete_then_valid_empty_sequence` | a live row remains after an empty snapshot | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.69 `test_operational_hashes_match_r68` | same `positions.py` pin | `HISTORICAL_HASH_PIN` |
| R.69 flat-snapshot test | local live row is retained | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.69 live-shape management test | recovery gate withholds the old pricing path | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.69 entry-tail skip | skipped by the test | `NOT_VERIFIED` |
| R.68 `test_15_bot_created_row_stays_manageable` | symbol-only delete is refused | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.68 `test_17_and_18` | `trading.py` hash is the current `b64d5887...` | `HISTORICAL_HASH_PIN` |
| R.68 disappear-path test | expected source text is gone | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.68 concurrency skip | skipped by the test | `NOT_VERIFIED` |

No failure in these suites was classified `GENUINE_BEHAVIOURAL_REGRESSION`. The schema-5 failures are the expected consequence of refusing a silent upgrade. R.75, R.74, and R.71 were green. R.76's three failures are the same three recorded at the end of R.77.

Suites that contain failures are not reported as green.
