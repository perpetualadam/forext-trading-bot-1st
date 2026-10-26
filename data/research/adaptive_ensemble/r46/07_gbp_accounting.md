# R.46 GBP accounting conflict matrix

No GBP P&L result is claimed. Production code was not repaired. The reported home currency selects GBP as the target denomination. It does not make any current function return that denomination.

| Path | What it does | Currency result | Classification | Conflict with the reported GBP account |
| --- | --- | --- | --- | --- |
| `quote_pnl_to_account_ccy` and `stop_risk_account_ccy` | Quote is USD: keep the amount. USD is base: divide by mid. | Approximate USD, as the function text states | `LOCALLY_VERIFIED_IMPLEMENTATION` | The reported home currency is GBP. This path does not convert USD into GBP. |
| `pnl_account_ccy` | Price change times units, then the USD approximation, using the exit price as the divisor for USD-base pairs | Approximate USD | `LOCALLY_VERIFIED_IMPLEMENTATION` | Same gap |
| `quote_pnl_to_usd` then `usd_to_gbp` | Builds a USD amount, then divides by GBP/USD mid or by `gbp_usd_fallback` 1.35 | GBP, by a shadow formula | `IMPLEMENTATION_ASSUMPTION` | Direction matches a GBP account. The 1.35 fallback is not a published rate. The 1.0% v20 markup is absent. Cross pairs that are neither USD-quote nor USD-base are not in the six. |
| `units_for_notional` | GBP notional times GBP/USD, then units = USD/price for USD-quote, or units = USD for USD-base | Whole units | `IMPLEMENTATION_ASSUMPTION` | Uses the reported currency's shape and an unverified stake identity |
| Fill parser | Reads fill `pl` as realised P&L in account currency | Whatever the broker put in that field | `LOCALLY_VERIFIED_IMPLEMENTATION` of the parser | The field's currency is `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED`. The parser does not check it against GBP. |
| Adapter exposure | Quote must equal the account currency, or the result is `exposure_conversion_missing` | No converted exposure | `LOCALLY_VERIFIED_IMPLEMENTATION` | For reported GBP, all six pairs fail closed. That is consistent with missing conversion. It is not the 1.0% rule. |
| Financing | Status `UNAVAILABLE`. Ledger kind `financing` is unresolved. | No amount | `LOCALLY_VERIFIED_IMPLEMENTATION` of the block | The charge is `UNKNOWN` |
| NAV and balance | Separate fields. Missing NAV is not taken from balance. | Account currency of the summary, when a summary exists | `LOCALLY_VERIFIED_IMPLEMENTATION` | The screen showed both at £97.15 once. The code must not collapse them because they were equal then. |
| Margin | `marginAvailable` is cached. Margin used and closeout are omitted. No closeout rule runs. | Not a GBP risk limit | `LOCALLY_VERIFIED_IMPLEMENTATION` | The v20 100% rule is a public candidate only |
| Spread | Shadow half-spreads and historical fill-minus-mid constants | Price units, then the shadow currency path | `IMPLEMENTATION_ASSUMPTION` | Not the "from 0.6 pips" phrase and not a current quote |
| R.27 fixture | Synthetic summary with currency USD | Test only | `SYNTHETIC_TEST_ONLY` | Not this GBP screen. The fixture identifier is not recorded here. |

## Inputs a future implementation would need

1. Confirmation that the home-currency field on a summary is GBP, matching the screen.
2. The stake-to-units identity, the pip distance, and the point distance.
3. Which conversion applies to realised P&L, financing, and margin: the 1.0% v20 settlement sentence, the 0.5% financing example, or another account rule.
4. The conversion price source and the side used for a profit versus a loss.
5. Whether fill `pl` is already GBP.
6. The v20 closeout fields to read, and confirmation that the 100% full-liquidation rule is the one on this spread-betting account.
7. A financing amount that is read or supplied for the hold, not a reused illustration such as −2.68%.
8. Removal of the USD approximation and of the 1.35 fallback only after those inputs exist. This stage does not remove them.

Until those inputs exist, the repository does not contain a correct GBP P&L for this account.
