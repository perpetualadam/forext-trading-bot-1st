# Evidence and broker-contract matrix

No live response exists. Every row below is a classification of the local schema and the local research record. Fixture numbers are not broker observations.

## Evidence labels

| Label | When it may be used |
| --- | --- |
| `SYNTHETIC_TEST_ONLY` | Offline fixture output only. It must never be copied into a broker-evidence file. |
| `READ_ONLY_RESPONSE_NOT_ACCOUNT_VERIFIED` | A future sanitised parse of a real response, if a later approval authorises the read. The label means the parser accepted fields. It does not mean the account is verified. |
| Explicitly verified account fact | Not available. No field in this matrix has that support. `ACCOUNT_VERIFIED` is forbidden. |

`account_specific_api_evidence` stays `NOT_PRODUCED` until such a future read exists. A future file would still omit the account identifier, the token, the `Authorization` header, and the full account URL.

Unresolved statuses that this preparation does not clear:

- `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`
- Spread-bet stake mapping: `NOT_VERIFIED`
- Token permissions: `UNKNOWN`
- Executable sizing: `NOT_CALCULATED`

## Six-pair matrix

The same source rules apply to `EUR_USD`, `GBP_USD`, `AUD_USD`, `USD_CAD`, `USD_CHF`, and `USD_JPY`. A future file would repeat the row only for names actually returned. A name that is absent stays `NOT_RETURNED` and is not borrowed from another pair.

| Field | Source if a future response contains it | Interpretation |
| --- | --- | --- |
| `instrument` | Instruments `name`, also required on the price row | Identity of the row. An unexpected name rejects the response. |
| `type` | Instruments `type` | Copied text. Not a spread-bet decision. |
| `pip_location` | Instruments `pipLocation` | Integer exponent used only in the spread arithmetic. Not a hardcoded pip size. |
| `display_precision` | Instruments `displayPrecision` | Display metadata. Not a rounding rule for orders. |
| `trade_unit_precision` | Instruments `tradeUnitsPrecision` | Precision metadata. Not the stake map. |
| `minimum_trade_size` | Instruments `minimumTradeSize` | Returned minimum, if present. Not an order quantity. |
| `maximum_order_units` | Instruments `maximumOrderUnits` | Returned ceiling, if present. Not a recommended size. |
| `maximum_position_size` | Instruments `maximumPositionSize` | Returned ceiling, if present. Not a recommended size. |
| `margin_rate` | Instruments `marginRate` | Returned rate, if present. Not a margin amount in GBP. |
| `minimum_trailing_stop_distance` | Instruments `minimumTrailingStopDistance` | Returned distance, if present. Not an instruction to place a stop. |
| `guaranteed_stop_mode` | Instruments `guaranteedStopLossOrderMode` | Returned mode, if present. Not a premium and not an instruction. |
| `financing_long_rate` | Instruments `financing.longRate` | Returned rate, if present. Not a GBP financing cost. |
| `financing_short_rate` | Instruments `financing.shortRate` | Returned rate, if present. Not a GBP financing cost. |
| `time` | Pricing `time` | The timestamp string that was returned. Not proof the quote is fresh. |
| `bid` | First pricing `bids[0].price` | One side of the snapshot. Not a fill. |
| `ask` | First pricing `asks[0].price` | One side of the snapshot. Not a fill. |
| `spread_pips` | Calculated: `(ask - bid) / 10**pipLocation` | Defined only for finite positive prices with ask not below bid and an integer pip location. Class would be a point-in-time width, not an executable spread. |
| `tradeable` | Pricing `tradeable` | Boolean as returned. False or missing means the quote is not usable. No substitute price. |
| `positive_units_factor` | `quoteHomeConversionFactors.positiveUnits` | Separate from the negative-units factor. Not copied across. |
| `negative_units_factor` | `quoteHomeConversionFactors.negativeUnits` | Separate from the positive-units factor. |
| `account_gain_factor` | First `homeConversions` entry `accountGain` | Separate from account loss. |
| `account_loss_factor` | First `homeConversions` entry `accountLoss` | Separate from account gain. |
| `quoted_conversion_currency` | First `homeConversions` entry `currency` | Currency named on that conversion entry. |
| `quoted_conversion_currency_is_account_home` | Local rule, always `NO` | The quoted currency is not treated as the account home currency. |
| `account_home_currency` | Not supplied by these two routes | Remains `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`. |
| `stake_settlement` | Not supplied | Remains `UNKNOWN`. Mapping status `NOT_VERIFIED`. |
| `evidence_class` | Local label | `SYNTHETIC_TEST_ONLY` offline. A future real parse would use `READ_ONLY_RESPONSE_NOT_ACCOUNT_VERIFIED` and still would not verify the account. |

## Account currency, pip value, stake, and financing

| Topic | Status | Why |
| --- | --- | --- |
| Account home currency | `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` | The two routes have no account-level currency field. A conversion `currency` is a quoted currency. The R.46 GBP screen is a historical user report, not an API response. |
| GBP conversion | Unresolved | Factors may be returned later. They are not assumed to be GBP, and `1.35` is forbidden. Public v20 markup sentences in R.45 do not identify this account's factor. |
| GBP pip value | `NOT_CALCULATED` | Needs home currency, stake or unit meaning, and a conversion. None of those is established. The ticket's £0.00 display is not zero risk. |
| Spread-bet stake mapping | `NOT_VERIFIED` | Quantity 1 is not £1 per pip. Instrument type does not decide the equation. The R.47 ticket, including 3,476 units, £0.84 trade value, and £0.03 margin, stays historical with `api_confirmation` NO. 3,476 is not a cap. £0.03 is not a fixed rate. |
| Financing cost | Not established | Returned long and short rates, if a future response has them, are rates. The historical panel stays in its own section with `api_confirmation` NO. It is not matched to the R.45 −2.68% illustration and not used as a backtest rate. |
| Executable size | `NOT_CALCULATED` | No size is proposed. Maximums and margin rates are not order instructions. |

## Prohibited evidence

- Synthetic fixture prices or rates inside a broker-evidence file.
- A hardcoded GBP rate, including `1.35`.
- A silent default for a missing field.
- Raw response bodies, tokens, account identifiers, or full account URLs.
- A trading recommendation or an executable quantity.
- Balance, NAV, positions, orders, or transactions.

## If Option B were ever authorised

Option B is deferred and is not authorised.

If a later approval added `GET /v3/accounts/{accountID}/summary`, the saved report would still exclude balance, NAV, margin used, margin available, unrealised P&L, position counts, order counts, and any position or order list. The account identifier and the full URL would stay out of the file. Only a locally verified currency field, if one were later documented and explicitly allowlisted, could be considered for home-currency evidence. That schema is **DOCUMENTATION_VERIFICATION_REQUIRED** and is not assumed here.

The full summary body would still have entered process memory. Exclusion from the report does not remove that exposure. The safer plan remains Option A, which does not request the summary.
