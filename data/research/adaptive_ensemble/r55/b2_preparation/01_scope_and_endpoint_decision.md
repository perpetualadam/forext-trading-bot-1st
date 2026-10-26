# Scope and endpoint decision

This document is a plan. It does not authorise a connection, a third request, or a change to the current allowlist.

The six names remain research-only: `EUR_USD`, `GBP_USD`, `AUD_USD`, `USD_CAD`, `USD_CHF`, `USD_JPY`. No strategy has established reliable profitability. Production deployment remains NO-GO.

A future HTTP 200, and a future parser acceptance, would show that those responses met the local checks. They would not prove the account, the product, the token permission, or an executable size. `ACCOUNT_VERIFIED` is not a permitted label.

## What a response can and cannot establish

| Question | Directly returned | Calculated from returned values | Inferred, not confirmed | Remains unknown | Separate broker-contract check |
| --- | --- | --- | --- | --- | --- |
| Can a credential authenticate to the intended account? | A future 200 or 401/403 would be the server's response to the exact requests that were sent. | None. | A 200 does not identify the legal entity, the product, or the person who holds the account. | Whether the token is limited to reading. Whether the account path is the intended account beyond the identifier the user typed. | The user must confirm, outside this program, that the identifier they type is the intended account. The program must not read a stored identifier. |
| Which of the six instruments are available? | Names present in a future instruments payload, after the allowlist rejects any name outside the six. | None. | Absence from one response is not a permanent broker prohibition. | Names that were not returned. Eligibility to trade them. | Product, sub-account, and client-category rules. |
| Which instrument fields are returned? | The fields the local parser already knows how to copy: `name`, `type`, `pipLocation`, `displayPrecision`, `tradeUnitsPrecision`, `minimumTradeSize`, `maximumOrderUnits`, `maximumPositionSize`, `marginRate`, `minimumTrailingStopDistance`, `guaranteedStopLossOrderMode`, and `financing.longRate`, `financing.shortRate`, `financing.financingDaysOfWeek` when that object is present. | None. A missing field stays `NOT_RETURNED` or `MISSING`. It is not filled in. | `type` equal to `CURRENCY` does not establish a spread-bet contract. | Fields the parser does not copy. The meaning of maximum units for this product. | Contract specification for minimum size, increment, and unit meaning. |
| Which quotes, bid/ask values, timestamps, and tradeability flags are returned? | Pricing `time`, the first `bids[0].price`, the first `asks[0].price`, and boolean `tradeable`, when those values are present. | The local parser keeps only the first bid price and the first ask price. Deeper book levels are not evidence. | A timestamp does not, by itself, prove the quote is fresh. No local age limit exists. | Quotes for instruments that were not returned. Whether `tradeable` false is temporary. | **DOCUMENTATION_VERIFICATION_REQUIRED** for any quote-age rule. Do not invent one. |
| Which spread calculations are mathematically supported? | None. The broker response used locally is bid and ask, not a spread field. | `(ask - bid) / 10**pipLocation`, only when bid and ask are finite and positive, ask is not below bid, and `pipLocation` is an integer. The result is a point-in-time width, not an executable spread. | A calculated width is not a published typical spread and not a fill price. | The spread the broker would apply to an order. Pip size must not be hardcoded as `0.0001`. | Public spread pages are indicative. They are not this account's executable spread. |
| Which conversion fields are available? | `quoteHomeConversionFactors.positiveUnits`, `quoteHomeConversionFactors.negativeUnits`, and each `homeConversions` entry's `currency`, `accountGain`, and `accountLoss`, when present. | None. Positive and negative factors stay separate. Gain and loss stay separate. | A factor is not a GBP pip value and not a stake. | Factors that are absent. They stay `NOT_RETURNED`. The value `1.35` must not be inserted. | Which markup, if any, is already inside the factor. R.45 records a public 1.0% v20 settlement sentence and a separate 0.5% financing example. Those sentences are not this account's factor. |
| What currency do those conversion fields refer to? | The `currency` string inside a returned `homeConversions` entry, copied only as `quoted_conversion_currency`. | None. | That string is not the account home currency. `quoted_conversion_currency_is_account_home` stays `NO`. | The account home currency. | R.46's user-reported GBP screen remains separate historical evidence. It is not an API field. |
| Can account home currency be established? | Not by the two allowlisted responses. Local schema has no account-level currency field on those routes. | No. | No. | `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`. | A broker screen or a separately authorised and separately documented field. Option B is not that authorisation. |
| Can spread-bet stake-to-API-unit mapping be established? | Not by these fields. | No. | `minimumTradeSize`, `tradeUnitsPrecision`, and instrument `type` do not choose between a unit equation and a stake-times-points equation. | `NOT_VERIFIED`. Quantity 1 is not £1 per pip. | The account product and the broker's stake convention. The R.47 ticket stays historical, with `api_confirmation` NO. |
| Can GBP pip value be established? | No. | No calculation is permitted. A GBP value would need a confirmed home currency, a confirmed stake or unit map, and a confirmed conversion. Those inputs are absent. | The R.47 display of £0.00 per pip is not zero risk. | `NOT_CALCULATED`. | Broker contract plus a later, separately authorised measurement. This plan does not produce a size or a pip value. |
| Can financing costs be established? | Instrument `financing.longRate` and `financing.shortRate` can be copied when present. | No cost is calculated. | A rate is not a GBP charge. The R.45 formula needs size, duration, an account-currency conversion, and a confirmed product rule. The historical panel, buy −2.43% / £16.75 and sell +0.42% / £2.90 per 100,000 units, has `api_confirmation` NO. | The charge in account currency for any holding period. | Product, posting rule, admin fee, and the day's rate. Do not match the panel to the R.45 illustration of −2.68%. |
| Can executable trade sizing be established? | No. | No. This plan calculates no position size. | Margin rate, minimum size, and a conversion factor do not form an order quantity. | `NOT_CALCULATED`. | Out of scope until home currency, stake mapping, and token permission are independently established, and until a later approval allows sizing. That approval is not this task. |

## Option A — keep the two-request design

Maximum two sequential GET requests, and only these:

1. `/v3/accounts/{accountID}/instruments`
2. `/v3/accounts/{accountID}/pricing`

The instruments query key is only `instruments`, with the six names in that fixed order. The pricing query keys are only `instruments` and `includeHomeConversions=true`.

This is the design already pinned in R.48, R.50, and R.53. This preparation does not change it and does not run it.

Option A could, after a future separate approval, record:

- Whether those two requests received HTTP 200.
- Which of the six names were present, and which allowlisted fields were present or `NOT_RETURNED`.
- The first bid, first ask, timestamp, and tradeable flag actually returned.
- A spread width only where the arithmetic above is defined.
- Conversion factors and a quoted conversion currency, still not treated as the home currency.

Option A would still leave unknown:

- Account home currency.
- Spread-bet stake mapping.
- GBP pip value.
- Financing cost in account currency.
- Executable size.
- Token permission.
- Whether the credential is the intended account, beyond the responses to these two paths.
- Account balance, NAV, open positions, and working orders. Option A does not request them.

## Option B — a possible later account-summary request

Candidate only: `GET /v3/accounts/{accountID}/summary`.

Local files do not contain the response schema for that path. Whether it returns a field that is the account home currency is **DOCUMENTATION_VERIFICATION_REQUIRED**. This task does not fetch that document.

R.51 records that no account-summary endpoint was added. R.48 allows only `instruments` and `pricing`. R.55 Boundary A and B1 exclude account discovery. The current output ban list already names `balance`, `nav`, `positions`, `orders`, and `transactions` as forbidden evidence keys.

Exposure if Option B were later sent, even before its schema is locally verified:

- The response would be an account summary. Until a local schema says otherwise, it must be treated as able to carry balance, NAV, margin, positions, orders, and other account-financial fields.
- Those values would enter process memory if the body were read, even if a later report deleted them.
- A report that copied any of them would widen the saved evidence far beyond instrument definitions and a price snapshot.
- Adding the path would change the request count and the allowlist. That requires a new written approval and new offline tests. This preparation does not implement either.

Option B is not assumed to be necessary, safe, or approved. It is not added.

## Recommendation

**Option A.**

Option B is **deferred**. It is not part of the plan that this preparation would hand to a later approval.

Rationale: the only request shape already specified, hash-pinned, and fail-closed in local source is the two GET design. It can answer instrument presence, returned fields, quotes, and arithmetic spreads. It cannot honestly answer home currency, and local research already forbids treating a conversion currency as that answer. Widening the read to an undocumented summary would add sensitive financial data in exchange for a field that has not been verified locally.

Under Option A, home currency, stake mapping, GBP pip value, financing cost, token permission, and executable size remain unverified. Under Option B, those same facts remain unverified until a local schema review and a separate approval exist. This document supplies neither.
