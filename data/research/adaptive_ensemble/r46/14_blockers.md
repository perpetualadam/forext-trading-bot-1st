# R.46 remaining blockers

The reconciliation is complete as a classification exercise. The account contract is not fully verified. Every row blocks practice orders and live orders. Economic evaluation stays blocked while the stake map, the GBP pip value, or pair eligibility is unknown.

| Blocker | Class | Why it still blocks |
| --- | --- | --- |
| Stake versus units | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | No evidence equates one v20 unit with one pound per point. |
| Minimum and increment | `UNKNOWN` | No size step was published or displayed. |
| GBP value of one pip | `UNKNOWN` | Local pip size is a price increment. |
| Pair eligibility | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | The default list is not a permission. Five names were not on the spread-bet page. |
| Production USD path versus reported GBP | `CONFLICTING_EVIDENCE` | Not repaired. |
| Shadow 1.35 fallback versus the 1.0% v20 candidate and the 0.5% financing example | `CONFLICTING_EVIDENCE` | Three conversion treatments. None is confirmed on a fill. |
| Displayed Live versus the practice default in source | `CONFLICTING_EVIDENCE` | The environment value was not read. Neither word authorises an order. |
| Spot-FX name comment versus reported spread betting | `CONFLICTING_EVIDENCE` | The identifier used on the ticket is unconfirmed. |
| Pair margin rate and client category | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | Caps are not this account's rate. |
| v20 closeout applicability to this spread bet | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | The bot does not apply it. The page scope is mixed. |
| Guaranteed-stop product scope, distance, and premium | `CONFLICTING_EVIDENCE` on scope. `UNKNOWN` on the numbers. | Ticket evidence is missing. |
| Financing rate | `UNKNOWN` | Formula only. |
| Fill `pl` currency | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | Reported account currency is GBP. The field was not read. |
| Current balance, NAV, and margin | `USER_REPORTED_ACCOUNT_SCREEN` for one historical pair of figures | Not current, and not margin available. |

OANDA One rules are not blockers for this profile. They are excluded. Importing them would create a new blocker.
