# R.84 official OANDA contract

Retrieved on 26 October 2026 without credentials and without an authenticated trading call.

- Transaction definitions: `https://developer.oanda.com/rest-live-v20/transaction-df/`
- Trade endpoint, including close examples: `https://developer.oanda.com/rest-live-v20/trade-ep/`

## Fields

| Field | Documented type | Optional | Sign evidence |
| --- | --- | --- | --- |
| `OrderFillTransaction.id` | `TransactionID` | Present on a transaction | Identifier, not a quantity |
| `OrderFillTransaction.orderID` | `OrderID` | The ID of the filled order | Distinct from `tradeID` |
| `OrderFillTransaction.units` | `DecimalNumber` | "The number of units filled" | Full-close example `"-100"`. Partial-close example `"10"`. The schema sentence does not state a sign rule |
| `OrderFillTransaction.instrument` | `InstrumentName` | Name of the filled instrument | Not a quantity |
| `OrderFillTransaction.accountID` | `AccountID` | Account that owns the transaction | Not a quantity |
| `OrderFillTransaction.clientOrderID` | `ClientID` | Only if the client assigned one | A client label |
| `OrderFillTransaction.requestID` | `RequestID` | Request that generated the transaction | Not documented as idempotency |
| `tradesClosed` | `Array[TradeReduce]` | Only if the fill closed trades | Full-close example uses this array |
| `tradeReduced` | `TradeReduce` | Only if the fill reduced an open trade | Partial-close example uses this object. It is one object, not an array |
| `tradeOpened` | `TradeOpen` | Only if the fill opened a trade | A fill can also carry a reduction. The schema allows the fields to describe different effects |
| `TradeReduce.tradeID` | `TradeID` | ID of the trade reduced or closed | Not `orderID` |
| `TradeReduce.units` | `DecimalNumber` | "The number of units that the Trade was reduced by" | Schema wording reads as a magnitude. Full-close example stores `"-100"`. Partial-close example stores `"10"` |
| Close request `units` | string, default `ALL` | Positive decimal or `ALL` | The request says the units must be positive. That is the request, not the fill |
| `relatedTransactionIDs` | array of `TransactionID` | IDs created while satisfying the request | Linkage, not a second unit count |
| `lastTransactionID` | `TransactionID` | Most recent account transaction | Not the closed quantity |
| `clientExtensions` | `ClientExtensions` | Client data | Not broker idempotency |

## What the two examples actually show

The partial-close example closes 10 units of USD_CAD trade `6397`. `orderFillTransaction.units` is `"10"` and `tradeReduced.units` is `"10"`. There is no `tradesClosed` array.

The full-close example closes EUR_USD trade `6395`. `orderCreateTransaction.units`, `orderFillTransaction.units`, and `tradesClosed[0].units` are all `"-100"`. There is no `tradeReduced` object.

In both examples the TradeReduce quantity has the same sign as the fill quantity. The schema sentence and the full-close example do not use the same sign convention. This stage records both and does not treat either one as a universal rule.

## Direction

The pages do not label the original trade as BUY or SELL. This bot's existing rule is that closing a long requires a negative fill and closing a short requires a positive fill. Under that existing rule, the full-close example matches a long close and the partial-close example matches a short close. That direction mapping is the bot's existing check plus the examples. It is not a sentence on the OANDA page.

## What is not established

`clientExtensions.id`, `clientOrderID`, and the order comment `"idempotent client order"` are not documented as broker-side idempotency. `requestID` identifies a request. A client label is not proof that OANDA rejects a duplicate PositionClose.

No page consulted here says a fill may be counted twice when both `tradesClosed` and `tradeReduced` repeat the same trade. The field descriptions say each field is provided for its own effect. This stage does not sum both.
