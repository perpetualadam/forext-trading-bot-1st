# R.76 broker entry identity contract

Classifier: `classify_entry_response` in `forex_bot/broker_entry_evidence.py` line 63.

These values are not interchangeable:

| Value | Source used here | Used as the managed trade id |
| --- | --- | --- |
| Client correlation id | `clientExtensions.id` and the journal `client_order_id` | No |
| Broker order id | `orderCreateTransaction.id`, otherwise fill `orderID` | No |
| Order-fill transaction id | `orderFillTransaction.id` | No |
| Broker trade id | `orderFillTransaction.tradeOpened.tradeID` or one item of `tradesOpened` | Yes, only when the state is a single confirmed open |
| `lastTransactionID` | present on some bodies | No |

`_parse_open_fill` still returns the fill transaction id as its third element. `record_entry_response` does not copy that element into `broker_trade_ids`.

A manageable position requires all of:

- the fill account, when present, equals the account passed to the classifier
- the fill instrument equals the journal instrument
- the fill client extension, when present, equals the journal client id
- the fill units sign matches BUY or SELL
- exactly one opened trade
- opened units equal fill units
- absolute fill units equal requested units
- no `tradesClosed` and no `tradeReduced`

Anything else is recorded and not published. The function does not submit a close.

A retrieved fill with a different id or instrument is `ENTRY_EVIDENCE_CONFLICT`. A failed lookup is not proof that the broker rejected the entry. The capture path does not clear a complete order-create body because a later read failed.

An instrument net is not a trade id. `load_startup_broker_view` (`forex_bot/startup_recovery.py` line 38) copies units onto a trade only when that instrument has exactly one trade id. Two trade ids stay separate and are not given the net units. Test 72 covers that case.
