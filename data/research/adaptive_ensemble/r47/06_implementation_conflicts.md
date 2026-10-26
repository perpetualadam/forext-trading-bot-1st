# R.47 implementation conflict matrix

Production code was not modified. `MAX_POSITION_UNITS` was not changed. Other fail-closed controls remain: inactive strategies, the removed quant stub, RL `UNAVAILABLE` on an unverified state, missing NAV not copied from balance, `exposure_conversion_missing` when the quote is not the account currency, and financing rows unresolved. Those controls are not a position-size cap.

| Topic | Ticket or R.46 profile | Current implementation | Class |
| --- | --- | --- | --- |
| Quantity | UI quantity 1 on a units heading. Unsubmitted. | Orders are sized in units. `units_for_notional` returns whole units. | `USER_REPORTED_TICKET_DISPLAY` versus `LOCALLY_VERIFIED_IMPLEMENTATION`. API identity is `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED`. |
| One unit as £1 per pip | Pip text 0.00 GBP and trade value 0.84 GBP contradict that reading at two decimals. | The code never treats one unit as £1 per pip. It multiplies units by price distance and then uses a USD or shadow-GBP path. | The £1-per-pip reading is rejected for this display. The code's unit equation is still unproven against the API. |
| Pip size | Not printed as a price increment. The money line is 0.00 GBP. | 0.0001 for EUR/USD. | `LOCALLY_VERIFIED_IMPLEMENTATION`. Broker pip and point remain `UNKNOWN`. |
| Price precision | Not printed. | 5 decimals for EUR/USD. | `LOCALLY_VERIFIED_IMPLEMENTATION`. Broker precision remains `UNKNOWN`. |
| Position cap | 3,476 is an estimate, not a cap. Quantity 1 is not a minimum. | `cap_position_units` returns the request unchanged when `MAX_POSITION_UNITS` is missing or not positive. The default passed to that helper is 0. | `LOCALLY_VERIFIED_IMPLEMENTATION`. Critical before any trading: there is no positive unit clamp in the default. This does not mean every other safeguard is absent. |
| Risk budget | 97.15 GBP margin available is not a budget. | Portfolio stop-risk helper defaults to 5% of the equity argument when the environment value is unset. Shadow defaults use percents of a simulated NAV, including `starting_nav_gbp` 97.15. | `IMPLEMENTATION_ASSUMPTION`. Applying either percent to the snapshot is not authorised. |
| Stop | Normal, with Price and Pips inputs. No distance shown. | `MIN_STOP_DISTANCE_PRICE` defaults to 0 when unset. Stop risk is then computed in approximate USD. | `CONFLICTING_EVIDENCE` on currency. Minimum distance is `UNKNOWN`. |
| GBP conversion | Trade value is labelled GBP. The rate is not shown. | Production path stops at approximate USD. Shadow divides by GBP/USD or 1.35. Public candidate is mid ± 1.0% for v20 and v20 MT4. Financing example used 0.5%. | `CONFLICTING_EVIDENCE` |
| Margin available | Displayed 97.15 GBP | Parser stores `marginAvailable` and does not treat it as a limit. Closeout fields are not applied. | `USER_REPORTED_TICKET_DISPLAY` versus `LOCALLY_VERIFIED_IMPLEMENTATION`. The v20 100% rule remains scope-limited. |
| Financing | Not on the ticket | `FINANCING_STATUS = UNAVAILABLE` | `UNKNOWN` charge. Fail-closed in reconciliation. |
| Fill P&L currency | Not on an unsubmitted ticket | Parser treats fill `pl` as account currency | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` |

The production USD path remains in conflict with a GBP-labelled ticket. The shadow GBP path remains in conflict with the unpublished 1.35 fallback. Neither path is repaired.
