# Sanitised response schema

Label on every row: `SYNTHETIC_TEST_ONLY`.

The session keeps these fields when the parser returns them. A missing field is `NOT_RETURNED`. Nothing is inferred.

Instrument: name, type, pip location, display precision, trade-unit precision, minimum trade size, maximum order units, maximum position size, margin rate, minimum trailing-stop distance, guaranteed-stop mode, financing long rate, financing short rate.

Pricing: timestamp, bid, ask, spread in pips from that instrument's pip location, tradeable status.

Conversions, kept apart: positive-units factor, negative-units factor, account-gain factor, account-loss factor, and the quoted conversion currency. The quoted conversion currency is not treated as the account home currency. Each row sets `quoted_conversion_currency_is_account_home` to NO and `account_home_currency` to `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`.

`stake_settlement` is `UNKNOWN`. No executable size is calculated. The shadow value 1.35 is not inserted.

The synthetic example is `06_synthetic_session.json`. Its prices and rates are fixture values, not OANDA observations.
