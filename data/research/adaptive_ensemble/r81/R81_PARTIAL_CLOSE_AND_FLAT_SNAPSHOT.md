# R.81 partial close and flat snapshot

Evidence class: executed `test_12` and `test_14`.

## Partial close

The synthetic fill closes 400 of 1000 units and the transaction body reports `tradesClosed` of 400 on trade `T2`. The state is `CLOSE_PARTIALLY_CONFIRMED`. The in-memory position units stay 1000. A repeat uses the same operation id and does not add a PositionClose. The partial row is a different trade id from the earlier ambiguous T1 row, so the ambiguous obligation is not reused as the partial case.

`R81_PARTIAL_CLOSE_PRESERVED`: PASS. The partial close is not marked fully confirmed.

## Flat snapshot

After one ambiguous PositionClose, a fresh process starts with `COMPLETE_EMPTY`. The journal still reports `CLOSE_OUTCOME_AMBIGUOUS`. The process does not submit and does not print a full confirmation. An empty open-trade list is not treated as proof that this close operation filled.

A second fresh process starts with the trade still present. It also does not submit and does not confirm the close. `network_permit` remains 1.

`R81_FLAT_SNAPSHOT_NOT_CLOSE_CONFIRMATION`: PASS.
