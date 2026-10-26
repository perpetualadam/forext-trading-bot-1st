# R.46 v20 spread-betting applicability

The target profile is the user-reported v20 spread-betting account. Public rules are assigned below. OANDA One rules are listed so they stay out of the specification. No public page was reopened. Dates and scope limits are the R.45 record. Effective dates remain `UNKNOWN`.

No R.45 source was a single sentence that both named v20 and stated a spread-betting contract term without a CFD heading or a mixed product page. The class `PUBLICLY_DOCUMENTED_V20_SPREAD_BET` therefore has no row. The screen report is what joins "v20" and "spread betting" for this profile. That join is `USER_REPORTED_ACCOUNT_SCREEN`, not a public contract clause.

## Candidate rules for this profile

These are v20 rules from R.45. They may be used later only as candidates, and only after a product document or a ticket shows they apply to this spread-betting account.

| Rule | Class | Why it is only a candidate |
| --- | --- | --- |
| Margin uses the current mid of the home/instrument conversion. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | Stated for v20 and v20 MT4. The spreads page heading is CFD markets. |
| Closeout percent = half of margin used / NAV mid. At 100% or higher, all open positions are liquidated and contingent orders on them are cancelled. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | The 100% dial matches v20. The page also describes CFDs. |
| Settlement of realised P&L, fees, and charges when the quote is not the home currency: mid plus or minus 1.0%. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | The sentence is limited to v20 and v20 MT4. It was not recorded as spread-bet-only. |
| Financing posted daily, usually at 5pm ET. FX amount uses size, the funding rate, 365, duration, and conversion. Weekend FX is usually tripled on Wednesday. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | v20 timing is stated. The financing page's spread-bet scope was not isolated from CFD text. The daily rate was not retrieved. |

## Spread-betting product statements that do not name v20

| Statement | Class |
| --- | --- |
| The customer does not own the underlying. Long and short are directional wagers. Profit requires a move beyond the spread. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Platforms include web, iOS, Android, TradingView, and MT4. MT5 cannot place a spread bet. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Marketing hours are 22:00 GMT Sunday to 22:00 GMT Friday, subject to the hours page's daylight-saving and holiday caveat. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Forex spread betting is described as commission free. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| EUR/USD is given an indicative spread "from 0.6 pips". | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| The spread-betting page says guaranteed stops are available on forex, indices, and gold. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |

## CFD-only material, excluded from the target specification

| Material | Why it stays out |
| --- | --- |
| The 76.6% retail CFD loss warning | CFD risk warning |
| MT5 indicative prices on the spreads page | The spread-betting page says MT5 cannot place a spread bet |
| Forex CFDs session, New York Sunday 17:05 to Friday 16:59, and the 100,000-unit standard lot | Published under the Forex CFDs heading |
| MT4 lot-size note for CFD trades on an MT4 account | CFD trades |
| Guaranteed-stop page wording "available on CFDs" | Conflicts with the spread-betting page. Neither page gives a forex premium. |
| Share and ETF CFD commission percentages | Different product |
| Retail margin-rates page heading "Retail CFD margin rates", with no forex card | Not a spread-bet instrument card |
| CFD forex Key Information Document | R.45 kept it separate from the named spread-bet forex document, which was not opened |

## OANDA One, excluded from the target specification

| Rule | Treatment |
| --- | --- |
| Margin locked from the sided price at execution | Not a v20 rule. Not imported. |
| Coverage percent closing at 50% by repeatedly closing the largest losing trade | Not the v20 100% full liquidation. Not imported. |
| FX financing accruing in unrealised P&L until the position closes | Not the v20 daily posting. Not imported. |
| The 1.0% settlement sentence's exclusion of OANDA One | Recorded so the 1.0% figure is not silently extended to OANDA One. It still does not prove the figure for this spread bet. |

## Still account-specific

Instrument eligibility, stake-to-units mapping, minimum size, increment, GBP value of one pip, the pair's margin rate, client category, guaranteed-stop distance and premium, the day's financing rate, and the currency field on a fill. The screen did not display any of those.
