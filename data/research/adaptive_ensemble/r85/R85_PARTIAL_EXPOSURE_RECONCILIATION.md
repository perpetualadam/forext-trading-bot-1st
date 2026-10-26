# R.85 Partial Exposure Reconciliation

Evidence: executed `execute_startup_sequence` on disposable journals after a real `run_guarded_live_close`. The broker object was synthetic. Confirmed units came from the R.84 parser reading `tradeReduced`.

Baseline: original 1000, confirmed 400, journal remaining 600, durable units 1000, memory units 1000, state `CLOSE_PARTIALLY_CONFIRMED`, permit consumed, ratchet 40.

| Broker observation | Executed result | Manageable |
| --- | --- | --- |
| Complete view, 600 units | `units_mismatch` | no |
| Complete view, 1000 units | `outstanding_CLOSE_PARTIALLY_CONFIRMED` | no |
| Complete view, 400 units | `units_mismatch` | no |
| Complete view, 0 units | `units_mismatch` | no |
| Complete view, 1200 units | `units_mismatch` | no |
| Opposite direction, units -600 | `direction_mismatch` | no |
| `COMPLETE_EMPTY` | `broker_flat_unattributed` | no |
| `INCOMPLETE` and empty | startup `RECOVERY_BLOCKED` | no |
| Target trade absent, other instrument present | `multiple_or_missing_trades` plus `broker_only` | no |
| Wrong account binding | `account_mismatch` | no |
| Wrong instrument on the only trade | `multiple_or_missing_trades` | no |
| Wrong trade id | `trade_id_mismatch` | no |
| `STALE` | startup blocked; row evaluator also non-authoritative | no |
| `REQUEST_FAILED` | startup blocked | no |
| Duplicate copies of the same trade | `multiple_or_missing_trades` | no |
| Extra unrelated GBP_USD trade | target stays `outstanding_CLOSE_PARTIALLY_CONFIRMED`; stored trade id stays `T1` | no |

BUY, SELL, and USD_JPY each confirmed 400 and kept remaining 600. The SELL fill and reduction were positive. The BUY and USD_JPY fill and reduction were negative. The parser accepted those documented signs.

The 600-unit view is consistent with journal remaining and inconsistent with durable original units. Recovery quarantines it. It does not choose the smaller number and it does not rewrite the journal. Startup did not submit a close. Generation stayed 1. One durable position row remained.

`COMPLETE` in this table is the label supplied by the test. It is not a freshness proof.
