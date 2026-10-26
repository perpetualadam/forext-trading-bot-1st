# R.46 reconciliation with R.44 and R.45

R.44 classified the account contract from local code and could not name the product. R.45 separated public v20, OANDA One, CFD, and spread-bet material and left the account unknown. R.46 adds the user-reported screen and does not promote it to an API confirmation.

| R.44 blocker | R.45 outcome | R.46 outcome | What changed |
| --- | --- | --- | --- |
| Product and jurisdiction | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | `USER_REPORTED_ACCOUNT_SCREEN` for the profile: OANDA, Live, v20, spread betting, GBP. Public rules stay scope-limited. | The target profile is now stated. API permission is not. |
| Instrument eligibility | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | Unchanged | The screen did not list pairs. |
| Stake versus units | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | Unchanged. Documented as the primary blocker. | No factor was chosen. |
| Minimum and increment | `NOT_FOUND` | `UNKNOWN` on this account | Still absent from public text and from the screen. |
| Pip value in GBP | `NOT_FOUND` | `UNKNOWN` | Code pip size remains a price increment. |
| GBP conversion | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | Same public candidate, plus `CONFLICTING_EVIDENCE` against the USD production path and the 1.35 shadow fallback | Reported home currency makes GBP the target denomination. No path implements the 1.0% v20 sentence. |
| Margin and closeout | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | v20 100% rule kept as a candidate. OANDA One 50% excluded from the profile. | The screen named v20, so the other closeout machine is out of the specification. Applicability to spread betting is still limited. |
| Stops | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | Unchanged | Ticket distance and premium are still unknown. The CFD versus spread-bet guaranteed-stop clash remains. |
| Overnight financing | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | v20 daily posting is the candidate. OANDA One accrue-until-close is excluded. | The day's rate is still unknown. |
| Weekend financing | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | Unchanged candidate: Wednesday triple unless a holiday moves it | Not an amount |
| Fees and current spread | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | Unchanged | "From 0.6 pips" is not a fill. No quote was requested. |
| Transaction currency | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | The reported account currency is GBP. The fill field is still unverified. | The parser's assumption is not confirmation. |

Public formulas that can inform a later specification, after the checklist items exist: the unit-based v20 margin formula, the v20 100% closeout, the FX financing formula, the Wednesday triple, and the 1.0% v20 settlement markup. They are not applied in the bot or in a backtest. The £97.15 snapshot does not unlock them.

R.45 completion still stands. Its public-network permission was not reused.
