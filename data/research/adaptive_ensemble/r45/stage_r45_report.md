# STAGE R.45 — PUBLIC OANDA UK SPREAD-BETTING DOCUMENTATION RESEARCH REPORT

Classification: `R45_PUBLIC_OANDA_DOCUMENT_RESEARCH_COMPLETED`

This classification means the authorised public pages were reviewed and the R.44 blockers were reconciled. It does not verify the account. It does not authorise trading.

## Branch, HEAD, and preservation

Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`. Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The working tree was already dirty and those unrelated changes were left in place. R.24–R.44 evidence is present. Six strategies stayed inactive. The quant stub stayed `quant_stub_removed`. RL on an unseen state stayed `UNAVAILABLE`. Research lifecycle code is not imported by `bot_loop.py` or `ai_ensemble.py`. No production source was edited.

## Official public sources and retrieval dates

Retrieved 2026-10-21, about 15:59 UTC, from `www.oanda.com` and `help.oanda.com` only. No page displayed a publication or effective date. Effective date is `UNKNOWN` for every source.

Reviewed: the UK spread-betting page, the UK legal index, spreads and margin, the retail margin-rates URL, financing costs, charges, the margin-required FAQ, the guaranteed-stop page, and hours of operation. The legal index title is OANDA Europe LTD. The spreads page says OANDA (Europe) Limited and the FCA. The help page says OANDA Europe Limited.

Not retrieved: guessed URLs for forex, margin rules, terms of business, and sub-account differences returned 404. The pip FAQ returned a browser gate and not the article. The retail margin-rates page rendered the heading "Retail CFD margin rates" and no forex card. The spread-bet forex Key Information Document is named on the legal index and was not opened, because its file URL was not in the index text. No API host, login page, form, or price feed was used.

## Spread betting and CFDs

OANDA Europe Limited publishes a UK spread-betting sub-account. The customer does not own the underlying. Long and short are directional wagers, and profit requires a move beyond the spread. The same public site also describes CFDs. The 76.6% retail-loss warning is a CFD warning. The spread-betting page lists OANDA web, iOS, Android, TradingView, and MT4, and states that MT5 cannot place a spread bet. Indicative prices on the spreads page are sourced from MT5, so they are not spread-bet executable prices. Marketing hours are 22:00 GMT Sunday to 22:00 GMT Friday. The detailed FX session, Sunday 17:05 to Friday 16:59 New York with a six-minute break, is published under the heading Forex CFDs. Those clocks are separate. The tax sentence on the spread-betting page is not applied to the user.

## v20 and OANDA One

v20 margin uses the current mid price. Closeout percent is half of margin used divided by NAV mid, and at 100% or higher the account liquidates open positions and cancels contingent orders on them. Financing is posted daily, usually at 5pm ET.

OANDA One margin uses the sided top-of-book price at execution and stays constant in home-currency units. Coverage is equity divided by margin, and at 50% or below the largest losing trade is closed and the check repeats. For most instruments, including FX, financing accrues in unrealised P&L until the position closes. Commodities are posted daily.

The FAQ sentence about margin closeout percent moving toward 100% matches v20. It does not match the OANDA One 50% coverage dial. A later specification has to name the sub-account before it uses either rule. Public product availability is not permission for this account.

## Six-instrument contract findings

EUR/USD is the only one of the six named on the spread-betting page, as an indicative spread "from 0.6 pips". That phrase is marketing. Margin-example arithmetic uses 0.0001 as one pip for EUR pairs. GBP/USD, AUD/USD, USD/CAD, USD/CHF, and USD/JPY are not named as spread-bet instruments. GBP/USD appears as a conversion pair in a GBP-account example. No retrieved example defines a USD/JPY pip as 0.01. Local five-decimal and three-decimal formatting remains a code convention.

The retail margin card did not render, so no pair is assigned to the major 3.33% class or the non-major 5% class. Minimum size, increment, price precision, GSLO distance, and GSLO premium were not published for these pairs. A CFD "all FX except TRY" hours row groups them and does not confirm spread-bet hours. Spread-bet availability for the five unnamed pairs is `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED`.

## Stake and sizing

Retrieved pages describe size in units: 1,000, 10,000, 100,000, 200,000, and 1,000,000. Under Forex CFDs, one standard lot is 100,000 units for FX except TRY, and an MT4 lot note applies to CFD trades on an MT4 account. No page states that a v20 forex spread bet is entered as GBP per point, or that one unit equals one pound per pip. Stake-to-units mapping, minimum size, and increment are `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED`. No sizing code was changed.

## Margin and closeout

Retail FCA caps on the spreads page: major forex 30:1 and 3.33% margin; non-major forex and gold 20:1 and 5%. Professional major forex is a separate 1.0% and 100:1 table, and the retail cap does not apply to professionals. Professional terms are not applied. Help text: margin needed equals margin rate times quantity times the instrument-to-home conversion. v20 uses current mid. OANDA One uses the sided price at execution. Worked examples are hypothetical and use a GBP home currency. One illustration applies a 3.33333% EUR/GBP example rate inside an EUR/USD figure. That rate is not this account's EUR/USD rate.

The bot parses available margin and does not apply a closeout rule. These pages cannot validate that missing check, cannot choose the sub-account, and cannot assign a pair to a class. No rate was copied into code.

## Financing and weekend treatment

FX financing is size times the funding rate, divided by 365, times duration, times conversion into the account currency. The funding rate is the tom-next swap plus an admin fee. Other FX pairs, the residual row after TRY and the named CZK, HUF, SAR, THB, and ZAR pairs, carry a 1% admin fee. The six pairs sit in that residual row only because they are absent from the named rows. The tom-next part changes daily. A worked long EUR/USD rate of −2.68%, including the 1% fee, is an illustration for one unnamed day. No rate table was downloaded. Positions open at 5pm ET are overnight. FX typically settles T+2, so weekend financing is usually tripled on Wednesday, and a holiday can move that day. v20 posts daily. OANDA One FX accrues until close. Today's rate is not treated as a 2025 or 2026 historical rate.

## Fees and GBP conversion

The spread-betting page says forex spread betting is commission free. Share and ETF CFD commission percentages are a different product. Deposit and withdrawal fees are not charged by OANDA; a bank might charge. Inactivity can be up to £20 per client per month after 12 months without trading, with the conditions on the charges page. A GSLO premium is charged only if the stop is triggered. The premium for these pairs is on the ticket, and the GSLO page itself scopes guaranteed stops to CFDs while the spread-betting page says they exist for forex.

When the quote currency is not the home currency, the charges page converts realised P&L, adjustments, fees, and charges at mid plus or minus 1.0%, and limits that sentence to v20 and v20 MT4. The financing example uses a 0.5% markup. Those percentages stay separate. OANDA One is outside the 1.0% sentence. The production path still approximates USD. The shadow path still converts through GBP/USD or the 1.35 fallback. The public pages use GBP as an example and do not settle this account's currency or the stake map. The conflict was not repaired.

## R.44 blocker reconciliation

`ACCOUNT_VERIFIED` is not used.

| Blocker | Outcome |
| --- | --- |
| Product and jurisdiction | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Instrument eligibility | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` |
| Stake versus units | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` |
| Minimum and increment | `NOT_FOUND` |
| Pip value in GBP | `NOT_FOUND` |
| GBP conversion | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Margin and closeout | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Stops | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Overnight financing | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Weekend financing | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Fees and current spread | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Transaction currency | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` |

Public formulas can inform a later specification only after product, sub-account, client category, and home currency are confirmed. They stay unused in the bot and in backtests.

## Remaining account-specific unknowns

Legal entity on the actual account, spread bet versus CFD, practice versus live, v20 versus OANDA One, retail versus professional, home currency, eligible symbols, minimum and increment, stake-to-units map, the margin rate on each pair, which closeout dial is live, which conversion markup applies, the financing posting rule and the day's rate, GSLO distance and premium, and the currency field on a fill. A later redacted product sheet can answer the words printed on that sheet. Current ticket and transaction facts would need a separately authorised read-only check. That check was not built.

## Tests and preservation

Attempt 1: every offline suite exited 0 except R.10, which failed 1, passed 68, and skipped 5 after `WinError 5` on the R.10 synthetic safety file. Attempt 2, R.10 only: 69 passed, 5 skipped, and `WinError 5` did not appear. Both attempts are in `pytest_r10_attempts.txt`. `live_safety.py` was not edited. R.28 PostgreSQL scripts were not run.

## Recommended R.46 direction

Do not start R.46 from this stage. If a later stage is authorised, keep it to one route: a user-supplied redacted product sheet, or a separately approved read-only account check with a no-order rule. Do not download candles, do not insert the 0.6 pip phrase or the 3.33% class cap into a backtest, do not repair the USD-versus-GBP conflict, and leave the R.42 range rule unchanged.

PRODUCTION DEPLOYMENT: NO-GO

PRACTICE ORDERS: NOT AUTHORISED

LIVE TRADING: NOT AUTHORISED

ROLLBACK: NO-GO
