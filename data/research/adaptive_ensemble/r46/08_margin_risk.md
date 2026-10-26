# R.46 margin and risk dependencies

The historical £97.15 snapshot is used only to show the scale of a denomination error. A USD approximation, a 1.35 fallback, or a unit count treated as pounds-per-point would misstate risk against a balance of that size. The figure is not turned into a stake, a lot, a leverage, or a position. Available margin is not inferred from it. The amount is not assumed to be still available.

| Control | What exists | Classification | Trading blocker |
| --- | --- | --- | --- |
| GBP risk limits | Shadow percents of a simulated NAV. Production stop risk is approximate USD. | `CONFLICTING_EVIDENCE` | Yes. No verified GBP risk limit. |
| Initial margin | Public candidate formula and retail class caps. No pair rate. No client category on the screen. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | Yes |
| Margin availability | Parsed when a summary is fetched. Not a limit. Not read in this stage. | `LOCALLY_VERIFIED_IMPLEMENTATION` of the parser | Yes. The snapshot is not margin available. |
| Margin closeout | v20 candidate is 100% and full liquidation. The bot does not apply it. OANDA One 50% is excluded from this profile. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | Yes |
| Stop restrictions | Slippage is described publicly. Distance and guaranteed-stop premium are not known for these pairs. `MIN_STOP_DISTANCE_PRICE` defaults to 0 in `trading.py` when unset. | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | Yes |
| Financing exposure | Fail-closed as unavailable. Formula is a candidate. Rate is unknown. | `LOCALLY_VERIFIED_IMPLEMENTATION` of the block | Yes |
| Currency conversion | Three local treatments, plus a public 1.0% v20 candidate and a separate 0.5% financing example. | `CONFLICTING_EVIDENCE` | Yes |
| Broker-reported P&L | Parser treats fill `pl` as account currency and does not prove the currency is GBP. | `LOCALLY_VERIFIED_IMPLEMENTATION` of the parser | Yes |

Existing fail-closed behaviour stays in place: missing NAV is not copied from balance, quote exposure that is not in the account currency returns `exposure_conversion_missing`, financing rows stay unresolved, strategies stay inactive, the quant stub stays removed, and RL stays `UNAVAILABLE` on an unverified state. None of that is weakened so that £97.15 can be traded.

Practice orders stay unauthorised. The displayed environment word Live does not authorise a live order. The code default practice, which applies only when the environment value is unset, conflicts with the displayed word and was not read from the environment.
