# STAGE R.47 — EUR/USD TICKET EVIDENCE AND GBP SIZING SPECIFICATION REPORT

Classification: `R47_EURUSD_TICKET_GBP_SIZING_SPEC_COMPLETED`

The redacted ticket was analysed and a research-only GBP sizing specification was written. The risk engine was not implemented. The account contract is not fully verified. `ACCOUNT_VERIFIED` is not used. The original screenshot was not stored.

## Branch, HEAD, and preservation

Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`. Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The working tree was already dirty and those unrelated changes were left in place. R.24–R.46 evidence is present. All six strategies stayed inactive. The quant stub stayed `quant_stub_removed`. RL on an unseen state stayed `UNAVAILABLE`. Research lifecycle code stayed disconnected. No production source was edited. No network request was made. No account identifier was recorded.

## Redacted ticket observations

User-reported, unsubmitted EUR/USD market-order ticket on an interface identified as Live. Class `USER_REPORTED_TICKET_DISPLAY`. No broker clock was in the redacted fields.

Quantity 1. Heading "Units Available". Units available 3,476. Trade value 0.84 GBP. One pip 0.00 GBP. Margin required 0.03 GBP. Margin available 97.15 GBP. Stop type Normal, with Price and Pips inputs. The Submit control was not used.

Margin available 97.15 GBP is a third displayed field beside the R.46 historical balance and NAV of £97.15. The three labels stay separate. None of them is a risk budget.

## Units interpretation

The UI can show quantity 1 under a units heading. That does not define the API units field, the minimum, or the increment. The pip line is 0.00 GBP and the trade value is 0.84 GBP, so this display is incompatible with reading quantity 1 as £1 per pip. It does not prove the conventional base-currency equation, and it does not prove the spread-betting contract. The order was not submitted, so the broker did not accept or reject quantity 1. 3,476 is a point-in-time estimate, not a safe maximum.

## Pip-value rounding

GBP figures are printed to two decimals. The rounding mode is unknown. Under nearest-cent rounding, 0.00 GBP means a magnitude below half a penny, or at the half-penny boundary if that tie prints as 0.00. The tie is unknown. Exact zero sits inside the band and is not selected by the text. Under truncation, 0.00 means a non-negative amount below 0.01. Either way, the display is not zero exposure. The unrounded GBP value of one pip is missing. A conventional one-unit EUR/USD pip of 0.0001 USD is small enough to print as 0.00 GBP, including at the shadow fallback 1.35, and so are many other conversions. The display does not identify which one.

## Margin display

0.03 GBP is the ticket estimate for quantity 1, not a general rate and not a reserve guarantee. Nearest-cent bounds on margin divided by trade value run roughly from 2.96% to 4.19%, which contains the published 3.33% cap and other rates. Truncation bounds start near 3.5% and leave 3.33% outside. The unknown rounding mode therefore neither confirms nor rejects 3.33%. An illustrative floor of 97.15 / 3,476 sits near 0.02795 GBP and would also print as 0.03. That illustration is not a measured rate and does not make 3,476 an order size.

## GBP risk specification

The general identity is: quote-currency P&L before costs = signed base-currency quantity × price movement. GBP per pip then needs the pip distance and a quote-to-GBP conversion. A spread bet can instead be stake × point distance. The ticket does not decide which equation the API uses. Local code implements the units equation, then stops at approximate USD, while the shadow path divides by GBP/USD or by 1.35. Public v20 candidates remain the mid-based margin formula, the 100% closeout, the 1.0% settlement markup, and the daily financing formula. OANDA One rules stay out. No executable size was calculated.

## Existing bot conflicts

`cap_position_units` leaves the request unchanged when `MAX_POSITION_UNITS` is missing or not positive. That default is a critical pre-trading gap. It is not a claim that every other safeguard is absent: strategies are inactive, financing fails closed, and a non-GBP quote returns `exposure_conversion_missing`. The production path is still approximate USD against a GBP-labelled ticket. The 1.35 fallback is still not a published rate. `MIN_STOP_DISTANCE_PRICE` still defaults to 0. None of these was changed.

## Six-pair applicability

EUR/USD is the only pair with these numbers. GBP/USD, AUD/USD, USD/CAD, USD/CHF, and USD/JPY are not enabled by this ticket. A later pair would need its own trade value, pip value, margin, minimum, and eligibility. Shared questions, not shared answers, are whether the quantity control is units-labelled and whether GBP amounts print to two decimals.

## Future risk-engine requirements

No trade while any of the following is missing: the size-field meaning, an unrounded GBP pip value, a live conversion that is not a fallback constant, the minimum and increment, the margin and closeout rule, the stop restrictions, a conservative financing representation, or an explicit GBP risk budget. A printed 0.00 GBP is not zero risk. A missing positive size clamp is not acceptance. Fill currency must reconcile to GBP. Every failure is fail-closed. These rules are not implemented.

## Remaining verification

Still required: the words that define one unit, whether that quantity is the API units field, the minimum and increment, the unrounded pip value, the conversion markup, GBP stop risk, the margin rate and closeout, stop restrictions, financing, and fill currency. Another two-decimal photograph of the same pip line cannot supply the unrounded value.

## Tests and preservation

Attempt 1: every offline suite exited 0 except R.10, which failed 1, passed 68, and skipped 5 after `WinError 5` on the R.10 synthetic safety file. Attempt 2, R.10 only: 69 passed, 5 skipped, and `WinError 5` did not appear. Both attempts are in `pytest_r10_attempts.txt`. `live_safety.py` was not edited. R.28 PostgreSQL scripts were not run.

## Recommended R.48 direction

Do not start R.48 from this stage. If a later stage is authorised, keep it to one redacted EUR/USD instrument line or ticket detail that names the size unit and shows the pip value at more than two decimals. If the interface cannot show more than two decimals, record that limit and stop. Do not submit the order, request a credential, download candles, copy 3,476 or 0.03 into configuration, or repair the USD path. Leave the R.42 range rule unchanged.

PRODUCTION DEPLOYMENT: NO-GO

PRACTICE ORDERS: NOT AUTHORISED

LIVE TRADING: NOT AUTHORISED

ROLLBACK: NO-GO
