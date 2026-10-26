# R.73 Test Matrix

File: `data/research/adaptive_ensemble/r73/poc/test_r73_close_evidence.py`

The R.69 isolation harness is imported before `forex_bot`. The synthetic client accepts only `PositionClose`, `TransactionDetails`, `OpenPositions`, `OrdersPending`, and `TradeDetails`.

| Scenario | Test |
| --- | --- |
| 1. Full fill and local delete | `test_01_full_fill_allows_one_delete` |
| 2 and 17. Partial fill | `test_02_partial_fill_retains_and_blocks_retry` |
| 3. Zero confirmed units | `test_03_zero_confirmed_units` |
| 4. Rejection | `test_04_rejection_does_not_delete_and_names_rejection` |
| 5 and 6. Timeout | `test_05_and_06_timeout_is_ambiguous_and_blocks_retry` |
| 7 and 8. Connection and HTTP failure | `test_07_and_08_connection_and_http_errors_are_ambiguous` |
| 9. Missing fill | `test_09_missing_fill_transaction` |
| 10. Missing closed-trade rows | `test_10_missing_closed_trade_details` |
| 11. Wrong trade | `test_11_wrong_trade_id` |
| 12. Wrong instrument | `test_12_wrong_instrument` |
| 13. Wrong direction | `test_13_wrong_direction` |
| 14. Wrong account | `test_14_wrong_account` |
| 15. Duplicate closed-trade rows | `test_15_duplicate_trade_rows` |
| 16. Response id differs from retrieved id | `test_16_conflicting_transaction_body` |
| 18. Excessive units | `test_18_excessive_units` |
| 19. Two threads | `test_19_two_threads_submit_once` |
| 20 and 21. Second trigger, including weekend reason | `test_20_second_trigger_after_ambiguous_does_not_submit` |
| 22. Flat book during an ambiguous close | `test_22_empty_snapshot_preserves_ambiguous_close` |
| 23. Incomplete snapshot | `test_23_incomplete_snapshot_does_not_flat_the_book` |
| 24 and 25. Flat book and manual disappearance without an operation | `test_24_broker_flat_without_a_close_operation` |
| 26. Stop reference without a transaction body | `test_26_stop_reference_does_not_submit_or_delete` |
| 27. Observation | `test_27_observation_is_not_closed` |
| 28. Paper | `test_28_paper_close_semantics_stay_local` |
| 29. Missing trade id | `test_29_missing_trade_id_blocks_submission` |
| 30. Multiple trade ids | `test_30_multiple_trade_ids` |
| 31. In-memory restart | `test_31_restart_keeps_unresolved_blocker_in_memory` |
| 32, 33, and 34. Verification failure and repeat cycle | `test_32_and_33_verification_failure_blocks_repeat_reads` |
| 35. Two symbols | `test_35_two_symbols_can_close_concurrently` |
| SELL full fill | `test_sell_full_fill` |
| Gates, marker, call order | `test_source_wiring_and_gates` |
| 67% activation, pip size, empty snapshot class, pending stop | `test_profit_protection_and_r72_pending_stop` |

Timeout before a body and timeout after the request is counted are the same classification: the helper has started `PositionClose`, no body came back, and the outcome is ambiguous. The test does not pretend to know whether the broker committed the close.
