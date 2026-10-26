# R.75 Broker and Local Reconciliation

Recovery uses a caller-supplied view. It does not fetch OANDA. The view is the output a read-only snapshot classifier would have to produce. `reconciliation.py` was not edited. Its hash remains `852a6e2a4da35bce50e68f82cd2e625f25bf36a707a3ad258c3c9d09011a9dbd`. R.70 `_interpret_open_positions` is unchanged.

| Case | Decision | Close count | Delete |
| --- | --- | --- | --- |
| Matching open trade | `restored_managed` / `broker_trade_matches` | 0 | false |
| Broker trade absent (`COMPLETE_EMPTY`) | `broker_flat_unattributed` | 0 | false |
| No durable row, broker trade present | `classify_broker_discovery` observation | 0 | false |
| Different units | `units_mismatch` | 0 | false |
| Different direction | `direction_mismatch` | 0 | false |
| Different trade id | `trade_id_mismatch` | 0 | false |
| Different account binding | `account_mismatch` | 0 | false |
| Different instrument, or two trades on one instrument | `multiple_or_missing_trades` | 0 | false |
| Outstanding ambiguous close | `outstanding_CLOSE_OUTCOME_AMBIGUOUS` or `journal_position_disagreement` | 0 | false |
| Fully confirmed close | `awaiting_finalisation` | 0 | false |
| Incomplete, malformed, stale, failed, or unknown snapshot | `broker_snapshot_not_authoritative` | 0 | false |

An instrument-level net is not accepted as a trade id. The view must carry `trade_id`. A flat snapshot does not delete the local row and does not confirm a transaction. Missing transaction history is not treated as proof that no close occurred. Units on the durable row are not rewritten from the broker view.

`test_restart_cases_stay_closed` covers the single-trade mismatches, the flat and incomplete classifications inside `test_recovery_matrix`, and a journal instance that disagrees with the durable row.
