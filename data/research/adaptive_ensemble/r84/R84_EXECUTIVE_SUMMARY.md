# R.84 executive summary

Classification: `R84_OANDA_CLOSE_CONTRACT_PARTIALLY_VERIFIED`

Production trading remains NO-GO. R.85 was not started.

The R.83 baseline matched. The close parser now accepts the official full-close shape, where `tradesClosed[].units` is negative and matches the fill, and the official partial-close shape, where `tradeReduced.units` is positive and matches the fill. A negative TradeReduce beside a positive fill is still rejected. The same reduction is not counted twice. Wrong account, instrument, trade, direction, and transaction id do not fully confirm.

The schema sentence says TradeReduce units are the number of units the trade was reduced by. The full-close example stores a negative number. Those two sources were not collapsed into one universal sign rule. That is why this stage is partial even though the documented fixtures and the operational restart tests passed.

`entry_journal.py` and `positions.py` are unchanged. `profit_protection.py` is unchanged. One additional edit stops `_apply_verified` from replacing the account binding with the classifier label `matched`, so the current owner can remove a fully confirmed position. The R.83 epoch fence still refuses a stale owner.

R.82 `test_16_unit_validation_matrix` and R.83 `test_13_closed_unit_contract` now fail one assertion each. Both expected every negative `tradesClosed` value to raise. That expectation is obsolete for a signed value that matches the fill. The historical files were not edited. R.81 through R.78 remain green. Older failure counts match the R.83 baseline.
