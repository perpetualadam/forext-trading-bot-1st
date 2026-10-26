# R.73 OANDA Close Response Review

The installed SDK request is `PositionCloseRequest` in `oandapyV20.contrib.requests`. Its constructor accepts `longUnits`, `shortUnits`, and optional client-extension dicts. The endpoint is `PUT v3/accounts/{accountID}/positions/{instrument}/close`.

The operational body is built in `_submit_position_close_body` (`forex_bot/oanda_exec.py` line 397). It sends only the unit field for the position side. Client extensions are not attached. The SDK fields are labels. This repository does not show the broker rejecting a second close because the same extension id was reused, so broker-enforced idempotency is not claimed.

`BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`

The reader accepts these response objects when present:

- `longOrderFillTransaction`, `shortOrderFillTransaction`, `orderFillTransaction`
- cancel and reject transactions on the long, short, or plain names

Two fill objects are a duplicate, not a full close. A reject or cancel without a fill is `CLOSE_REJECTED_CONFIRMED` and does not fetch a transaction. A fill id is then loaded with `TransactionDetails` through `oanda_client._oanda_request`.

Realised P/L is not used as proof of units. Price movement is not used. HTTP success is not used.
