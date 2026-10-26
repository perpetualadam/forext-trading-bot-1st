# R.49 sanitised output schema

A future successful parse may keep only these fields. Anything else is dropped. No raw response is stored. No balance, NAV, position, order, transaction, or account identifier is stored.

Instrument row: name, type, pip location, display precision, trade-unit precision, minimum trade size, maximum order units, maximum position size, margin rate, minimum trailing-stop distance, guaranteed-stop mode, financing long rate, financing short rate, and financing days as day name plus days charged.

Price row: instrument, timestamp, bid, ask, spread in pips, tradeable, `positiveUnits`, `negativeUnits`, and home conversions with `currency`, `accountGain`, and `accountLoss` kept as separate values. The spread label would be `POINT_IN_TIME_API_SNAPSHOT` only after a real snapshot. None was taken.

The plan row records method GET, the host, the path pattern with `{accountID}`, the query pattern, a 5-second timeout, zero retries, redirects false, body empty, and stream false. It does not record a full URL.

No trade size is calculated from these fields. The R.47 ticket values stay historical rounded displays. Instrument metadata alone would still not prove the spread-bet stake map. No order is used to test the minimum size.
