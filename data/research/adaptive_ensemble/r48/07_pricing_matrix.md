# R.48 pricing and conversion matrix

No pricing snapshot was taken. There is no `POINT_IN_TIME_API_SNAPSHOT` for the account. No bid, ask, spread, or conversion factor was copied into a strategy parameter.

| Instrument | Time | Bid | Ask | Tradeable | Spread | positiveUnits | negativeUnits | accountGain | accountLoss |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EUR_USD | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` |
| GBP_USD | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` |
| AUD_USD | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` |
| USD_CAD | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` |
| USD_CHF | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` |
| USD_JPY | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` | `NOT_RETRIEVED` |

The parser keeps `positiveUnits` apart from `negativeUnits`, and `accountGain` apart from `accountLoss`. It does not copy one into the other. It drops ladder liquidity and closeout prices. None of those rules was applied to a live payload.
