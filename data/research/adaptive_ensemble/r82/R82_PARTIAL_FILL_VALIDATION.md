# R.82 partial-fill validation

`test_16_unit_validation_matrix` calls `apply_transaction_body` on synthetic transaction dicts. These are not OANDA records. Requested size is 1000 unless noted. BUY close transactions use a negative fill-unit field so the direction check passes. The zero case uses fill units `-1` and closed units `0`, so the zero result is the closed-unit total rather than a direction mismatch.

| Closed units | State | Confirmed | Remaining |
| --- | --- | --- | --- |
| 999 | `CLOSE_PARTIALLY_CONFIRMED` | 999 | 1 |
| 1000 | `CLOSE_FULLY_CONFIRMED` | 1000 | 0 |
| 0 | `CLOSE_RECONCILIATION_REQUIRED` | 0 | 1000 |
| 1200 | `CLOSE_RECONCILIATION_REQUIRED` | 1200 | `None` |
| -100 | `CloseReadError` | Not stored | Not stored |

| Identity fault | Result |
| --- | --- |
| Empty transaction id | `CloseReadError` |
| Trade id `T-OTHER` | `CloseReadError` |
| Account `001-002-0000001-009` | `CloseReadError` |
| Instrument `GBP_USD` against EUR_USD | `CloseReadError` |
| Same trade id twice in `tradesClosed` | `CloseReadError` before the units are added |

SELL with positive fill units and 400 closed units returns confirmed 400 and remaining 600. USD_JPY with 400 closed units returns remaining 600. JPY handling here is instrument identity and unit arithmetic. Pip size was not changed.

`test_15` is the operational 400-unit path: one PositionClose, journal confirmed 400, remaining 600, and a replay does not send a second close or add the 400 again.

Two distinct partial confirmations for one close operation are not supported. A second call returns the blocking row. No completion protocol was added.
