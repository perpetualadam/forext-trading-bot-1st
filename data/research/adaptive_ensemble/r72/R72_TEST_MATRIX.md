# R.72 Test Matrix

File: `data/research/adaptive_ensemble/r72/poc/test_r72_broker_protection.py`

The harness is `data/research/adaptive_ensemble/r69/poc/isolation.py`, imported before `forex_bot`. The broker object is a synthetic `request` method. Unexpected endpoint names raise `IsolationBreach`. `OANDA_MAX_RETRIES=1`.

| Scenario | Test |
| --- | --- |
| 1, 5, 7, 21. Pending EUR_USD BUY stop | `test_01_pending_stop_buy_eur` |
| 2. Pending take-profit | `test_02_pending_take_profit` |
| 3. Both pending | `test_03_both_pending` |
| 4, 6. USD_JPY SELL pending stop | `test_04_sell_usd_jpy_pending_stop` |
| 8. Explicit null stop and TP | `test_08_explicit_null_stop_is_confirmed_absence` |
| 9. Missing stop field | `test_09_missing_stop_field_is_not_absence` |
| 10. Missing trade id | `test_10_missing_trade_id` |
| 11. Missing account | `test_11_missing_account` |
| 12. Missing client | `test_12_missing_client` |
| 13. Timeout | `test_13_timeout` |
| 14. Request exception | `test_14_request_exception` |
| 15. Null body | `test_15_null_body` |
| 16. Malformed body | `test_16_malformed_body` |
| 17. Non-finite price | `test_17_nonfinite_price` |
| 18. Invalid units | `test_18_invalid_units` |
| 19. Duplicate order ids | `test_19_duplicate_order_ids` |
| 20. Contradictory pending plus filling id | `test_20_contradictory_order_state` |
| 22. Cancelled | `test_22_cancelled_stop_is_not_protection_or_fill` |
| 23. Rejected | `test_23_rejected_stop` |
| 24. Filled stop with transaction id on the order | `test_24_filled_stop_is_recorded_and_does_not_delete` |
| 25. Filled TP with transaction id on the order | `test_25_filled_take_profit_linked` |
| 26. Filled order for another trade | `test_26_fill_for_another_trade_is_conflict` |
| 27. Closed trade, null sections | `test_27_broker_flat_without_fill_attribution` |
| 28. Partial fill | `test_28_partial_fill_is_not_a_confirmed_exit` |
| 29. Two trade ids | `test_29_multiple_trade_ids_are_not_aggregated` |
| 30. Observation import | `test_30_observation_import_is_not_promoted` |
| 31. Paper | `test_31_paper_local_price_is_not_broker_protection` |
| 32. Simulated, window_paper, synthetic | `test_32_simulated_window_and_synthetic_do_not_read` |
| 33. Older success after newer success | `test_33_older_success_does_not_overwrite_newer_success` |
| 34. Trade id changes during the read | `test_34_identity_change_discards_inflight_evidence` |
| 35. Row removed and observation imported during the read | `test_35_removal_and_reconcile_overlap_do_not_publish_or_promote` |
| Newer failure keeps the published success | `test_newer_failure_keeps_published_success` |
| Unknown kind and manual observation | `test_unknown_kind_and_manual_observation_are_refused` |
| Filled order with no transaction id | `test_unlinked_fill_is_not_attributed` |
| Local prices with no broker sections | `test_local_stop_does_not_confirm_protection` |
| Source wiring, gates, marker, unchanged hashes | `test_operational_source_wiring_and_unchanged_files` |
| Profit protection, R.70 snapshot, weekend flatten, R.68 refusal | `test_profit_protection_and_snapshot_regression` |

Every evidence test asserts the write-endpoint set is empty, the local row object is unchanged, the three authority flags are false, `broker_sl_tp_hit` is false, no permit file appears, and the isolation log has no `socket.connect`, `urlopen`, or `psycopg2.connect`.

The operational function under test is `record_management_protection_evidence`, which `bot_loop.py` calls. The R.69 suite also entered `_evaluate_impl` and reached the new call.
