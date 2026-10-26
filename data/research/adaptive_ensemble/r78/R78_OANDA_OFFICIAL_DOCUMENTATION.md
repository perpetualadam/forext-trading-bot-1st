# R.78 OANDA official documentation

Retrieved 2026-10-25 from the public documentation site. No request was sent to `api-fxpractice.oanda.com`, `api-fxtrade.oanda.com`, or any account, order, trade, or transaction endpoint.

| Title | URL |
| --- | --- |
| Order Endpoints | https://developer.oanda.com/rest-live-v20/order-ep/ |
| Order Definitions | https://developer.oanda.com/rest-live-v20/order-df/ |
| Transaction Definitions | https://developer.oanda.com/rest-live-v20/transaction-df/ |
| Primitive Definitions | https://developer.oanda.com/rest-live-v20/primitives-df/ |

## Create Order

Endpoint: `POST /v3/accounts/{accountID}/orders`.

The published example "Create an Entry Order ... with Client Extensions" sends `order.clientExtensions.id`, `tag`, and `comment`. The sample response has HTTP 201, `Location` ending in `/orders/6373`, `lastTransactionID` `6373`, and `orderCreateTransaction.id` `6373`. The client id in that example is `my_order_100`. The order id and the client id are different values.

The response header list describes `RequestID` as "the unique identifier generated for the request". That is a server-generated request id. The page does not say the client can supply it to make a retry idempotent.

## Order specifier

`GET /v3/accounts/{accountID}/orders/{orderSpecifier}` documents an `OrderSpecifier`. The example requests `/orders/@my_order_100` and the sample order has `id` `6375`, `clientExtensions.id` `my_order_100`, and `replacesOrderID` `6373`.

What the page explicitly shows: a client id can be used as a lookup key by prefixing `@`. In the sample, that lookup returns an OANDA order id that is not the client id.

What it does not say: that posting the same client id twice is rejected, or that it cannot create two trades. The sample is a replace/lookup illustration. It is not a duplicate-POST test.

## OrderFillTransaction

Documented fields used by this audit, from Transaction Definitions:

| Field | Documentation status | Guarantee |
| --- | --- | --- |
| `id` | Transaction identifier | Not the order id and not the trade id |
| `orderID` | The id of the filled order | Not a trade id |
| `clientOrderID` | Optional `ClientID` | Present only if the client assigned one |
| `instrument` | Instrument name | Identity field |
| `units` | Decimal number of units filled | Sign carries direction |
| `price` | Deprecated | Not used as proof of a new trade |
| `tradeOpened` | Optional `TradeOpen` | Present only if a new trade was opened |
| `tradesClosed` | Optional array of `TradeReduce` | Present only if open trades were closed |
| `tradeReduced` | Optional `TradeReduce` | Present only if an open trade was reduced |
| `tradesOpened` | Not in this schema | The bot still treats a list defensively |

`TradeOpen.tradeID` is the opened trade. The page does not define a field that makes the order id usable as the trade id.

## Related identifiers

Create examples include `relatedTransactionIDs` and `lastTransactionID`. Their absence is not defined as success or failure. `classify_entry_response` does not treat either field as an entry outcome.

## How the code uses this

`classify_entry_response` in `forex_bot/broker_entry_evidence.py` reads `orderCreateTransaction`, `orderFillTransaction`, `orderCancelTransaction`, and `orderRejectTransaction`. The trade id comes only from `tradeOpened` or, defensively, `tradesOpened`. `broker_order_id` is stored separately. Lines 119–130 require `clientExtensions.id` or `clientOrderID` to equal the requested client id. Lines 160–165 reject a trade id that equals the order id.

This is a documentation comparison. It is not a broker execution.
