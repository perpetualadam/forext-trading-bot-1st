# R.47 mathematical GBP sizing specification

Research only. No order quantity is produced. The historical £97.15 figures are not a risk budget. The ticket does not prove the complete GBP spread-betting monetary map.

## 1. General mathematical relationships

These identities are `DERIVED_MATHEMATICAL_RELATION`. They are not broker terms.

For a price quoted as quote currency per one base currency:

- Price movement = exit price − entry price, in price units.
- Quote-currency P&L before costs = signed base-currency quantity × price movement.
- A pip is a stated price increment. It is not itself money.
- Quote-currency P&L for one pip = signed quantity × pip size.
- Home-currency P&L = quote-currency P&L × a conversion from the quote currency into the home currency, after whatever spread and markup the converter uses.
- GBP per pip = that home-currency result when the home currency is GBP and the move is one pip.
- Stop-loss money, before slippage and charges = GBP per pip × stop distance in pips, or the same product written as quantity × stop distance in price × conversion.
- Spread cost is the same identity on the bid/ask distance instead of the stop distance.
- Margin, when a rate applies to a converted quantity, has the shape rate × quantity × conversion. The rate is an input, not a consequence of the identity.
- Financing, when a rate applies to size over a day count, has the shape size × rate / day-count × duration × conversion. The rate is an input.
- A normal stop can fill at a price other than the stop price. Slippage is an extra price movement. It is not included by writing the stop into the formula.

The conventional units sentence is the quote-currency line above. It describes spot-style base-currency quantity. A spread-bet contract can define size as money per point, with a point that is not the code's pip, and with P&L equal to stake × point distance. That second contract is a different equation. Seeing a units label on one ticket does not decide which equation the broker uses in the API, in the fill currency, or after a conversion charge.

## 2. Locally implemented formulas

`LOCALLY_VERIFIED_IMPLEMENTATION` in the current code, and still an `IMPLEMENTATION_ASSUMPTION` relative to this ticket.

| Formula | Where | Result currency |
| --- | --- | --- |
| Quote P&L = signed units × price change, then USD-quote amounts stay and USD-base amounts divide by mid | `quote_pnl_to_account_ccy`, `pnl_account_ccy` | Approximate USD |
| Stop risk = distance × units, with the same USD-base division | `stop_risk_account_ccy` | Approximate USD |
| Shadow path divides that USD-shaped amount by GBP/USD mid or by 1.35 | `usd_to_gbp`, `stop_risk_gbp` | GBP by a local fallback |
| Whole units from a GBP notional via the same fallback | `units_for_notional` | Units |
| Pip size 0.0001, or 0.01 when the quote is JPY | `pip_size`, `research_pip_size` | Price increment |
| Price text 5 decimals, or 3 when the name contains JPY | `_format_oanda_price`, `format_broker_price` | Display precision |
| Units pass through when `MAX_POSITION_UNITS` is unset or not positive | `cap_position_units` | No clamp |
| Portfolio stop-risk cap defaults to 5% of equity when unset, and the equity's currency is the caller's | `configured_max_portfolio_risk_pct` | Not a verified GBP budget |
| Financing amount | Not implemented. Status `UNAVAILABLE` | No amount |

## 3. Publicly documented broker rules

From R.45, class `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS`. Not re-fetched. Not promoted by this ticket.

- v20 margin candidate: margin rate × quantity × mid conversion into the home currency.
- v20 closeout candidate: half of margin used / NAV mid, full liquidation at 100% or higher.
- v20 settlement candidate: mid ± 1.0% when the quote is not the home currency, stated for v20 and v20 MT4.
- Financing candidate: size × funding rate / 365 × duration × conversion, daily around 5pm ET, Wednesday triple for T+2 FX. The day's rate is unknown.
- A financing example used 0.5%. That percentage stays separate from 1.0%.
- A normal stop can slip. Guaranteed-stop distance and premium were not published for EUR/USD.

OANDA One rules stay out of the specification, as in R.46.

## 4. Screenshot-observed values

`USER_REPORTED_TICKET_DISPLAY`, EUR/USD, quantity 1, unsubmitted.

- Trade value text: 0.84 GBP.
- One-pip text: 0.00 GBP.
- Margin-required text: 0.03 GBP.
- Units-available text: 3,476.
- Margin-available text: 97.15 GBP.
- Stop type text: Normal. Inputs: Price and Pips.

These are display strings. They are not the unrounded inputs of the formulas above.

## 5. Account-specific unknowns

`ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` or `UNKNOWN`.

- Whether quantity 1 is one base-currency unit in the API body.
- The unrounded GBP value of one pip.
- The broker's pip size and point size for this spread bet.
- The conversion markup that produced the trade-value and pip-value text.
- The margin rate behind 0.03 GBP.
- Minimum size, increment, and whether the API would accept 1.
- Stop distance minimum, slippage, and guaranteed-stop terms.
- Financing on a hold.
- The currency of a fill `pl` field.
- Eligibility of the other five names.

## What the ticket does not prove

The conventional equation "quote P&L = signed base units × price move" is compatible with a two-decimal pip display of 0.00 for quantity 1, because one pip on one EUR/USD unit is 0.0001 USD, and 0.0001 USD is a small fraction of one penny in GBP. The same display is also compatible with any other contract whose GBP pip value is below one displayed penny. The ticket therefore does not establish the spread-betting monetary map. It does rule out reading this quantity as £1 per pip, because that reading would display about 1.00 GBP per pip rather than 0.00 GBP.
