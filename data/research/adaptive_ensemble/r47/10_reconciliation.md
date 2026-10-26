# R.47 reconciliation with R.44–R.46

R.44 found no GBP-per-point definition and three conflicting currency paths. R.45 found public unit language and no stake map. R.46 set the target profile to a user-reported OANDA Live v20 GBP spread-betting account and left the stake map as the primary blocker. R.47 adds one unsubmitted EUR/USD ticket. `ACCOUNT_VERIFIED` is not used.

| Prior blocker | After this ticket |
| --- | --- |
| Stake versus units | Still `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` for the API. The display rejects reading quantity 1 as £1 per pip, because the pip line is 0.00 GBP and the trade value is 0.84 GBP. The units heading is `USER_REPORTED_TICKET_DISPLAY`, not the order body. |
| Minimum and increment | Still `UNKNOWN`. An unsubmitted 1 does not prove either. |
| GBP per pip | The rounded text is 0.00 GBP. The unrounded value remains `UNKNOWN`. Exposure is not zero. |
| GBP conversion | The ticket labels money in GBP, which agrees with the reported home currency. The rate and the markup are not on the ticket. The USD path, the 1.35 fallback, the 1.0% candidate, and the 0.5% example remain `CONFLICTING_EVIDENCE`. |
| Margin | 0.03 GBP is a quantity-1 estimate. It does not identify the 3.33% class cap. Margin available 97.15 GBP is a new displayed field beside the R.46 balance and NAV figures. The three are not collapsed. |
| Closeout | Unchanged v20 candidate. Not shown on this ticket. OANDA One stays out. |
| Stops | Normal, with Price and Pips. Distance, slippage protection, and guaranteed-stop terms remain `UNKNOWN`. |
| Financing | Not on the ticket. Unchanged. |
| Pair eligibility | EUR/USD was displayable on this ticket. That is not a statement that an order would be accepted, and it says nothing about the other five. |
| Position clamp | `MAX_POSITION_UNITS` default 0 still means no clamp. The ticket's 3,476 is not the repair. |

No production formula was changed. No public rate was inserted into a backtest. The R.42 range rule is unchanged.
