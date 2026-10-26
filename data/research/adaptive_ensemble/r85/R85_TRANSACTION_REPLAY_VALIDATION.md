# R.85 Transaction Replay Validation

Evidence: executed `resolve_from_retrieved_transaction` on the partial close row. The parser itself was also called once for the documented negative `tradeReduced` shape and once for a positive fill with a negative reduction.

## Same transaction twice

The stored transaction `TX-R85` was applied again. Both calls returned `CLOSE_PARTIALLY_CONFIRMED`. Confirmed units stayed 400. Remaining units stayed 600. The second call did not add another 400.

## Same body, both reduction fields

`test_47` applied one body whose `tradeReduced` units were `-400` beside a fill of `-400`. Confirmed units were 400, not 800. Matching duplicate evidence inside one transaction is still counted once by the unchanged parser.

## Conflicting second transaction

A different id, `TX-OTHER`, carried a full `tradesClosed` of 1000. `resolve_from_retrieved_transaction` returned the existing `CLOSE_PARTIALLY_CONFIRMED` and left confirmed units at 400. It did not mark the close full. The observation reason is `conflicting_transaction_id`. This guard is outside the signed-unit parser. It refuses to replace a stored transaction id.

## Same id, wrong trade

Replaying `TX-R85` with `tradeID` `T-WRONG` left confirmed units at 400 and the state partial. The parser's trade-identity rejection was not allowed to replace the stored confirmation.

## Not implemented

Two successive partial closes that sum to the original position were not merged into a full close. A snapshot that arrives before or after the transaction was not used as the confirmed quantity. Those cases stay on the snapshot quarantine path.

Broker-enforced idempotency was not tested. Replaying a transaction id in this journal is not a broker guarantee.
