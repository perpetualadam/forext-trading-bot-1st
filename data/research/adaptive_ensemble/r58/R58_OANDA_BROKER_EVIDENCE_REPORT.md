# R.58 OANDA GBP spread-betting broker evidence

## 1. Executive conclusion

**Production trading remains NO-GO.**

OANDA’s official v20 documentation defines an API unit, for a v20 sub-account, as one unit of the base currency. OANDA Europe also says a v20 spread-betting sub-account is a separate account and is not the default. No official page states that a spread-betting sub-account changes that unit into a GBP-per-pip stake, and the REST v20 instrument type has no spread-bet value. The successful R.56 summary did not return an account type. This account’s product classification and stake-to-unit rule remain unproven.

The smallest metadata request that can fill the instrument fields is one read-only GET. It was not sent. It cannot, by itself, prove the stake rule or supply a fresh GBP conversion. Those still need a later pricing conversion read and a written answer from OANDA. Neither is authorised by this phase.

No OANDA request was made. No credential, permit, gate, R.56 file, or executable source was changed.

## 2. Verified official documentation

Pages read for this report:

| Source | What it establishes |
| --- | --- |
| https://help.oanda.com/uk/en/faqs/micro-lots.htm | OANDA Europe Limited. On a v20 sub-account, on the OANDA platform, “One unit is equal to one of the base currency in a currency pair.” The examples are “one unit of USD/CHF is equal to one dollar” and “one unit of EUR/USD is equal to one Euro.” The page does not mention spread betting. |
| https://www.oanda.com/uk-en/trading/standard-account/differences/ | On v20, spread betting is “Not by default. You can create a new sub-account with spread betting enabled.” v20 order volume on OANDA platforms is set in units. Margin and financing rules below are stated for v20, not as a separate spread-bet formula. |
| https://www.oanda.com/assets/documents/1918/MR-6396-OEL-sub-accounts-notable-differences-2025-01-29-V4.pdf | OANDA Europe PDF. Same spread-betting sentence, and the same v20 margin formula, as the UK differences page. |
| https://developer.oanda.com/rest-live-v20/account-ep/ | `GET /v3/accounts/{accountID}/instruments` returns `instruments: Array[Instrument]`. The query `instruments` is “List of instruments to query specifically.” The list “is dependent on the regulatory division” and “should be the same for all Accounts owned by a single user.” Documented errors are 400, 401, and 405. |
| https://developer.oanda.com/rest-live-v20/primitives-df/ | `Instrument`, `InstrumentFinancing`, `InstrumentType`, pip and size fields, guaranteed-stop fields, and `HomeConversionFactors`. |
| https://developer.oanda.com/rest-live-v20/account-df/ | Account and `AccountSummary` fields, including home `currency`, `NAV`, margin amounts, optional account `marginRate`, and `guaranteedStopLossOrderMode`. |
| https://developer.oanda.com/rest-live-v20/pricing-df/ and https://developer.oanda.com/rest-live-v20/pricing-ep/ | `quoteHomeConversionFactors`, `HomeConversions`, and `includeHomeConversions`. |
| https://www.oanda.com/uk-en/trading/financing-costs/ | UK financing formula, long and short rates, 5pm ET cutoff, and a GBP-account EURUSD example. |

`InstrumentType` is `CURRENCY`, `CFD`, or `METAL`. There is no spread-bet type. Account and `AccountSummary` have no documented spread-bet flag. `tags` are an array of strings with no documented vocabulary.

The earlier file `R56_FIRST_LIVE_DIAGNOSTIC_REPORT.md` records the aborted attempt: no broker request and the permit not consumed. The later sanitised log `real_diagnostic_logs/r56-phase6-r561f34518e0da44a79a0477cad84ee53a3-0001.json`, collected `2026-10-24T17:09:36Z`, is the successful read. It reports home currency GBP, `account_type` `NOT_RETURNED`, financing `FINANCING_NOT_VERIFIED`, pip location `NOT_ESTABLISHED`, and `STAKE_TO_UNIT_MAPPING_NOT_VERIFIED`. Both GETs received a broker response. Every quote was `non-tradeable`, timestamped `2026-10-23T20:59:05Z`. No order was produced. Those prices and the conversion numbers stored with them are not current rates.

## 3. Unit and spread-betting stake analysis

For an ordinary OANDA Europe v20 sub-account, the documented identity is:

- One API unit of `EUR_USD` is one euro.
- One API unit of `USD_CHF` is one US dollar.
- The same sentence covers a v20 sub-account generally: one unit is one unit of the base currency.

That is not proof for a spread-betting sub-account. The UK differences page treats spread betting as an account setting, not as a different instrument type, and it still describes v20 order volume as units. It never says those units are a GBP stake.

A GBP-per-pip or GBP-per-point stake is therefore not an API field. If the base-currency rule is later confirmed for this account, the stake is a result:

`GBP per pip = units * (10 ^ pipLocation) * quote_loss_factor_to_GBP`

The order’s `units` field would still be a count of base-currency units. Rearranging that identity gives the unit count for a chosen GBP stake. Until OANDA confirms the rule for this sub-account, that rearrangement is a hypothesis, not a sizing rule.

The regulatory division changes which instruments are offered. The instruments endpoint says so. GBP as home currency does not identify the division, and the live host used in R.56 does not either. The successful summary did not return an account type. Whether this sub-account is the spread-betting sub-account is `ACCOUNT_SPECIFIC_UNVERIFIED`.

The API exposes the metadata in sections 4 and 5. It does not expose a documented field that answers the stake question.

## 4. Exact proposed minimum GET

Do not send this request in this phase. Do not add it to the R.56 two-GET client.

```text
GET /v3/accounts/{accountID}/instruments?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF
```

One request, one account, six instruments, no body, no order. The `instruments` query is the documented filter, so the call does not need to download the whole instrument catalogue.

This GET is account-scoped. The documentation says the list should match the user’s other accounts in the same division. That sentence is not a substitute for reading this account’s payload, and it does not say a spread-bet sub-account and a CFD sub-account return the same stake meaning.

No second endpoint is required to obtain pip location, precision, minimum size, maximum size, instrument margin rate, or the instrument financing and guaranteed-stop objects, if the broker includes them. A second endpoint is required before a GBP risk figure can be called verified:

`GET /v3/accounts/{accountID}/pricing?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF&includeHomeConversions=true`

That pricing read is not part of the minimum metadata plan. It is the documented way to receive `homeConversions`. It must wait for a separate authorisation, and it is useless as a sizing rate while `tradeable` is false. The R.56 pricing response already carried deprecated `quoteHomeConversionFactors` on non-tradeable weekend prices. Those factors stay unused.

No documented read returns “this sub-account is a spread bet.” An extra account GET is not proposed.

## 5. Expected response fields

The `Instrument` schema in `primitives-df` defines every field below. The published `account-ep` example returns the core size and margin fields and omits financing and guaranteed-stop fields. Omission on a live response means the value is unavailable. It does not mean zero, and it does not mean `DISABLED`. `DISABLED` is an explicit enum value.

| Field | In the published example | Absence rule in the schema | What it does not prove |
| --- | --- | --- | --- |
| `name`, `type`, `displayName` | Yes | None stated | `type` cannot be “spread bet”. |
| `pipLocation` | Yes | None stated | A sample of `-4` or `-2` is not this account. Pip size is `10 ^ pipLocation`. |
| `displayPrecision` | Yes | None stated | Price decimals, not a stake increment. |
| `tradeUnitsPrecision` | Yes | None stated | Decimal places allowed on `units`. Not a GBP stake step unless the unit rule is confirmed. |
| `minimumTradeSize` | Yes | None stated | Smallest unit count. The example value `1` is not this account. |
| `maximumOrderUnits` | Yes | None stated | Maximum units on one order. |
| `maximumPositionSize` | Yes | None stated | The example value `0` is not defined as “no limit”. A live `0` stays unresolved. |
| `marginRate` | Yes | None stated | Instrument rate only. It is not the whole margin calculation. |
| `financing` | No | Not marked optional | `longRate`, `shortRate`, and `financingDaysOfWeek`. Rates are decimals: `0.05` means 5%. The cutoff clock is “set in the DivisionTradingGroup”, which this object does not include. |
| `guaranteedStopLossOrderMode` | No | Not marked optional | `DISABLED`, `ALLOWED`, or `REQUIRED` for this instrument. |
| `minimumGuaranteedStopLossDistance` | No | Not marked optional | Minimum distance in price units. |
| `guaranteedStopLossOrderExecutionPremium` | No | Present only when the instrument mode is not `DISABLED` | Price units, charged per unit of the trade if a guaranteed stop is triggered and filled. |
| `guaranteedStopLossOrderLevelRestriction` | No | Present only when the instrument mode is not `DISABLED` | Volume allowed inside a price window. |
| `commission` | No | Not marked optional | Home-currency commission per `unitsTraded`, if returned. |

`pipLocation`, precision, minimum size, maximum sizes, and `marginRate` are the fields this one GET is documented to return in the example. Financing and guaranteed-stop fields are documented in the schema and can be missing. A missing financing object does not verify a financing rate.

## 6. GBP conversion requirements

These identities assume the unproven base-currency unit. They are the mathematics to apply after that assumption is confirmed. They are not a calculation from the weekend quotes.

Quote-currency profit or loss for a price change `d` on `u` units:

`quote_pl = d * u`

That amount is in the quote currency: USD for `EUR_USD`, `GBP_USD`, and `AUD_USD`; JPY for `USD_JPY`; CAD for `USD_CAD`; CHF for `USD_CHF`. `GBP_USD` does not skip conversion. Its price profit is in USD even though its base currency and this account’s home currency are both GBP.

Home-currency profit or loss is the quote amount multiplied by the broker factor for that quote currency. The documented objects are:

- Deprecated, on each `ClientPrice`, and omitted when `includeHomeConversions` is present: `quoteHomeConversionFactors.positiveUnits` and `negativeUnits`. Each multiplies a quote-currency amount of that sign into home currency.
- Current pricing response, only when `includeHomeConversions=true`: `homeConversions[]` with `currency`, `accountGain`, `accountLoss`, and `positionValue`. `accountGain` covers positive realised profit and positive financing. `accountLoss` covers negative realised profit and negative financing.
- `HomeConversionFactors` in `primitives-df` is a different object, with `gainQuoteHome`, `lossQuoteHome`, `gainBaseHome`, and `lossBaseHome`. It is not what the R.56 pricing log stored.

A loss estimate uses the loss factor, not the gain factor. The two can differ. A mid-price approximation is the method OANDA states for v20 margin, not the method it states for displayed or realised profit. The UK differences page says displayed unrealised profit uses sided prices, and that realised home-currency profit “may also differ” because the quote-to-home conversion, including markup, is fixed at closure. A pre-trade factor is an estimate. It becomes settlement only when the broker applies the closing conversion.

For `USD_JPY`, `USD_CAD`, and `USD_CHF`, the required factor converts the quote currency directly to GBP. Dividing by the instrument price and then converting USD to GBP is an approximation. It is verified only if it matches the broker’s quote-currency factor.

Evidence required before a GBP risk figure is verified:

1. Written confirmation that one API unit on this sub-account is one base-currency unit.
2. A fresh `pipLocation` for that instrument from the instruments GET.
3. A fresh loss factor for the quote currency from a tradeable pricing response, using `accountLoss` when `includeHomeConversions=true`.
4. A tradeable bid and ask. The stop for a long is judged from the bid side, and the stop for a short from the ask side.
5. `minimumTradeSize` and `tradeUnitsPrecision`, and confirmation that no separate stake increment exists.
6. Rejection of the result when the rounded minimum size exceeds the GBP budget.

The weekend bids, asks, and stored factors fail item 3 and item 4. They are not conversion rates.

## 7. Margin and financing findings

OANDA Europe’s v20 formula, from the UK differences page and the 29 January 2025 OEL PDF, is:

`Margin_Used = Margin_Rate * Trade_Quantity * Instrument_To_Home_Currency_Conversion_Rate`

The conversion rate in that v20 rule is “the current mid-price for the Home/Instrument currency pair”, with the example “GBPUSD for a EURUSD trade in a GBP-denominated account.” Margin used is dynamic. It changes when that conversion changes. Margin calculations use mid prices so that a spread change alone does not change margin. The close-out percentage is `(50% * Margin_Used) / NAV_mid`, and close-out is at 100%.

The instrument `marginRate` is “the margin rate for this instrument.” The account `marginRate` is different: a client override, returned only when an override exists, whose effective account rate is “the lesser of this value and the OANDA margin rate for the Account’s division.” The position formula does not say whether its `Margin_Rate` is the instrument rate, the division rate, the override, or some combination. That interaction is `UNRESOLVED`.

UK financing page, for the scope that page states:

- Charge or credit = size or position value, times the funding rate, times duration, times the conversion into account currency.
- FX uses position size. The rate is annual. Divide by 365, then apply duration.
- Each instrument has a long rate and a short rate. A negative rate is a debit.
- v20 posts the cash daily, usually at 5pm ET. FX weekend financing is usually applied on Wednesday as three days, and holidays can move that.
- The page says the basis is the same “across open positions held on all accounts irrespective of the trading platform.”
- Its EURUSD example on a GBP account uses a size of 200,000 and converts a EUR amount through EURGBP, with a 0.5% markup on the midpoint in that worked example. The 0.5% figure is the example’s arithmetic, not a constant to add on top of an API factor.

The API `financing` object can return the long rate, the short rate, and `daysCharged` for each weekday. It does not return the 5pm ET clock. A rate in one response is a snapshot. The UK page says daily rates change and that indicative rates can differ from the finalised rate published after 5pm ET.

The financing page uses the words “spread bet/CFD price” for futures-based commodities, metals, and bonds. It does not give FX spread bets a separate formula. It also does not name this account. Spread-betting financing on this sub-account is `ACCOUNT_SPECIFIC_UNVERIFIED`.

A guaranteed-stop execution premium is a fee in price units per unit of the trade, and only if the instrument mode is not `DISABLED`. The distance restriction is also in the instrument schema. No official passage read for this report says that attaching a guaranteed stop changes the margin formula. That effect is `UNRESOLVED`.

## 8. Account-specific unknowns

| Item | Status |
| --- | --- |
| This sub-account is a spread-betting sub-account | `ACCOUNT_SPECIFIC_UNVERIFIED` |
| One API unit on this sub-account is one base-currency unit | `ACCOUNT_SPECIFIC_UNVERIFIED` |
| Home currency GBP | Reported by the later R.56 summary. Not re-read in this phase. |
| Pip location, precision, minimum and maximum units, instrument margin rate | Not returned by R.56. Available only from a future instruments response. |
| Financing rates and `daysCharged` for these six instruments | Not verified. The API field may be absent. |
| Division cutoff versus the published 5pm ET rule | `ACCOUNT_SPECIFIC_UNVERIFIED` |
| Guaranteed-stop mode, distance, premium, and any margin effect | Mode was not captured. Margin effect is not in the documents read. |
| Meaning of `maximumPositionSize` if the value is `0` | `UNRESOLVED` |
| Which margin rate the position formula uses when an account override also exists | `UNRESOLVED` |
| Fresh quote-to-GBP loss factors | The stored weekend factors are not current. |
| Separate stake increment | Not defined by `tradeUnitsPrecision`. |
| Charges or constraints that REST v20 does not return | Not proven absent. |

## 9. Evidence matrix

| R.57 blocker | Classification | Resolved by the one instruments GET |
| --- | --- | --- |
| v20 unit means one base-currency unit, as a general Europe v20 rule | `OFFICIAL_DOCUMENTATION_VERIFIED` | No. The page is not this account. |
| This account is spread betting, and the same unit rule applies to it | `OANDA_SUPPORT_CONFIRMATION_REQUIRED` | No. `InstrumentType` cannot say so. |
| GBP-per-pip stake expressed as API units | `OANDA_SUPPORT_CONFIRMATION_REQUIRED` | No. The GET returns unit counts, not a stake definition. |
| `pipLocation` for these six instruments | `ACCOUNT_SPECIFIC_API_REQUIRED` | Yes, if the field is present. The formula `10 ^ pipLocation` is already documented. |
| `displayPrecision`, `tradeUnitsPrecision`, `minimumTradeSize`, `maximumOrderUnits` | `ACCOUNT_SPECIFIC_API_REQUIRED` | Yes, if present. |
| `maximumPositionSize`, including a value of `0` | `UNRESOLVED` until the value is returned and `0` is defined | The GET can return the value. It cannot define `0`. |
| Quote-to-home loss and gain factors | `ACCOUNT_SPECIFIC_API_REQUIRED` | No. They come from pricing, and the stored copies are stale. |
| Sided profit versus mid-price margin, and settlement differing from the estimate | `OFFICIAL_DOCUMENTATION_VERIFIED` as v20 rules | No. |
| Instrument `marginRate` | `ACCOUNT_SPECIFIC_API_REQUIRED` | Yes, if present. |
| v20 margin formula and mid conversion | `OFFICIAL_DOCUMENTATION_VERIFIED` for the UK v20 statement | No. |
| Which rate applies when both account and instrument rates exist | `UNRESOLVED` | No. |
| Financing formula, long/short rates, and 5pm ET for UK v20 | `OFFICIAL_DOCUMENTATION_VERIFIED` for that page’s stated scope | No. |
| Financing values and weekday multipliers on this account | `ACCOUNT_SPECIFIC_API_REQUIRED` | Only if `financing` is present. Absence leaves it unverified. |
| Spread-bet financing is the same on this account | `OANDA_SUPPORT_CONFIRMATION_REQUIRED` | No. |
| Guaranteed-stop mode, distance, and premium | `ACCOUNT_SPECIFIC_API_REQUIRED` | Only if those fields are present. |
| Guaranteed stop changes margin | `UNRESOLVED` | No. |
| Bot fallback GBP rate `1.35` and quote profit treated as account currency | Code defect. The documented replacement is the broker loss factor, not a new constant. | No. |

## 10. Recommendation for the next action

Keep production trading stopped. Do not change the sizer yet. A code change that assumes base-currency units would repeat the R.57 failure if this sub-account does not use that rule.

The next evidence step, only after a separate authorisation, is the single instruments GET in section 4, together with sending `R58_OANDA_SUPPORT_ENQUIRY.md`. Do not send either as part of this phase. Do not extend the R.56 two-GET program to include the new endpoint.

After both answers exist, a separately authorised pricing read with `includeHomeConversions=true` can collect fresh loss factors, and only from tradeable prices. Until the support answer, the instruments payload, and a fresh loss factor agree, the bot still has no verified GBP position size.
