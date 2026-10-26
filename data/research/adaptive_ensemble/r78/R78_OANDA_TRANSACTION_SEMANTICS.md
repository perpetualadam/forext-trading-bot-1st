# R.78 OANDA transaction semantics

Compared with Transaction Definitions and Order Definitions on 2026-10-25. No broker call.

| Field | Status | Bot use |
| --- | --- | --- |
| `orderCreateTransaction` | Documented on the create response | Read by `classify_entry_response`. Its `id` becomes the order id when present. |
| `orderFillTransaction` | Documented | Required for a confirmed open. Missing fill is `ENTRY_OUTCOME_AMBIGUOUS`. |
| `orderCancelTransaction` | Documented | Without a fill, `ENTRY_REJECTED_CONFIRMED`. |
| `orderRejectTransaction` | Documented | Without a fill, `ENTRY_REJECTED_CONFIRMED`. |
| `tradeOpened` | Optional, singular `TradeOpen` | The only documented source of a new trade id. |
| `tradesOpened` | Not in the OrderFill schema | If a list is present and `tradeOpened` is absent, more than one item is `ENTRY_CONFIRMED_MULTIPLE_TRADES` and is not manageable. |
| `tradeReduced` | Optional, singular | Any reduction is `ENTRY_PARTIAL_OR_MIXED_EFFECT` and is not a clean open. |
| `tradesClosed` | Optional array | Any closure is the same mixed state. |
| `relatedTransactionIDs` | Present on create examples | Not an outcome by itself. |
| `lastTransactionID` | Present on create examples | Not an outcome by itself. |
| `clientExtensions` | On the order request and create transaction | `id` must match the requested client id when it is the observed client id. |
| `clientOrderID` | Optional on the fill | Accepted as the observed client id. If both it and `clientExtensions.id` are present and differ, the state is `ENTRY_EVIDENCE_CONFLICT`. |

Account, instrument, direction, and units are checked against the request. A different account, instrument, or sign is `ENTRY_EVIDENCE_CONFLICT`. Units that parse but do not equal the request are `ENTRY_PARTIAL_OR_MIXED_EFFECT`, including when a trade id is present. `manageable` stays false for that state.

Netting and hedging are represented by the optional open, reduce, and close objects. The classifier does not collapse several trade ids into one position. A market order that only reduces or closes an existing trade is not published as a new managed open.

Partial fills are not treated as a complete open. An order id is not copied into `broker_trade_id`. If those two ids are equal, the state is `ENTRY_RECONCILIATION_REQUIRED` with reason `order_id_is_not_trade_id`.

A retrieved fill whose id or instrument differs from the response fill is `ENTRY_EVIDENCE_CONFLICT`. An incomplete transaction history is not success. The investigation layer uses a separate classification for that case.
