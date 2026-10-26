# STAGE R.44 — OFFLINE BROKER CONTRACT EVIDENCE REVIEW REPORT

Classification: `R44_OFFLINE_BROKER_CONTRACT_REVIEW_COMPLETED`

This classification does not mean the OANDA account contract has been verified. No claim is `ACCOUNT_VERIFIED`.

## Preservation

Project root `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`, branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The working tree was already dirty. R.24–R.43 evidence is intact. All six strategies remain inactive. The quant stub remains `quant_stub_removed` and fail-closed. Reinforcement learning remains `UNAVAILABLE`. Research modules remain disconnected from production execution. Operational hashes are unchanged. `.env`, operational state, and private account documents were not opened. No broker, database, or network call was made.

## Sources reviewed

R.26, R.27, and R.43 reports; the G.3 request plan already cited in R.43; and the non-secret instrument, account, sizing, and shadow-cost source listed in `02_sources.md`. Synthetic fixtures were treated as fixtures. Raw G.3 pages, `data/ops`, and `v2_shadow` were left unopened.

## Verified implementation facts

The code targets OANDA v20 and chooses the practice or live host from `TRADING_MODE`. The default mode in source is `practice`. The six names are the default symbol list. Pip size in code is 0.0001 except 0.01 when the quote is JPY. Price formatting writes five decimals, or three when the name contains JPY. Sizing uses units. `account_core` keeps NAV and balance separate and does not copy a missing NAV from balance. Financing, fee, and transfer ledger kinds fail closed. A position whose quote currency differs from the account currency returns `exposure_conversion_missing`.

## Account-specific unknowns

Product, jurisdiction, practice versus live, instrument permission, stake, pip value, margin, closeout, stops, financing, fees, and current NAV are unknown. The shadow default `starting_nav_gbp = 97.15` is labelled `SIMULATED_SHADOW_NOT_BROKER`. It is not a verified balance and not a spread. `BASE_BALANCE` defaults to 10000 and is also not an account balance.

## Six-instrument contract matrix

| Instrument | Quote | Pip convention | Price format | `trading.py` value path |
| --- | --- | --- | --- | --- |
| EUR_USD | USD | 0.0001 | 5 decimals | Quote P&L treated as USD account currency |
| GBP_USD | USD | 0.0001 | 5 decimals | Same |
| AUD_USD | USD | 0.0001 | 5 decimals | Same |
| USD_CAD | CAD | 0.0001 | 5 decimals | Quote P&L divided by mid |
| USD_CHF | CHF | 0.0001 | 5 decimals | Quote P&L divided by mid |
| USD_JPY | JPY | 0.01 | 3 decimals | Quote P&L divided by mid |

Broker minimum size, increment, margin, leverage, hours, guaranteed stops, financing, weekend charges, and commission are unknown for every row. None of the six quotes is GBP, so the adapter's conversion check would reject them on a GBP account until a conversion exists.

## GBP accounting gaps

There is no GBP-per-point or GBP-per-pip implementation. Shadow code converts a USD notion into GBP and falls back to 1.35. `trading.py` stops at approximate USD. Those paths conflict. Realised fill `pl` is parsed as account-currency P&L without a verified currency. Margin used and closeout are not risk limits. Financing is explicitly unavailable.

## Risk and execution dependencies

Loss limits, exposure caps, reservation, and recovery are tested on synthetic fixtures. The R.27 success fixture used USD, NAV 10000, balance 10010, and a synthetic account id. Those tests do not make the execution path safe for this account. Margin, stop distance, stake, and financing still depend on unverified broker terms.

## Remaining blockers

Product and jurisdiction, instrument eligibility, stake versus units, minimum size, pip value, GBP conversion, margin and closeout, stop rules, overnight and weekend financing, fees and current spread, and transaction-currency reconciliation. Each blocks practice trading, live trading, and a GBP economic result. A public page cannot prove this account's permissions.

## Future verification options

Route A is a later user-supplied redacted product sheet, with no credentials and no account numbers. Route B is a separately authorised public-document read, which still cannot prove account access. Route C, an account-specific read, is not authorised. No broker client was created. The contract-fact schema leaves unknown fields null.

## R.27 and R.43 reconciliation

R.27 stays partial. R.43's checklist still stands. R.26's description of the old NAV-from-balance helper is historical: R.27 changed that helper, and the current parser matches the repair. Currency assumptions conflict across `trading.py`, the shadow GBP path, the "e.g. GBP" comment, and the USD fixture. The practice default conflicts with the G.3 live candle label. The spot-FX name comment conflicts with the spread-bet intention. None of those conflicts was smoothed over.

## Tests

The R.8–R.42 suites passed on the first run, including R.10 with 69 passed and 5 skipped. `WinError 5` did not appear in this run. There was no retry. Safety assertions were not weakened.

## Recommended R.45 direction

Do not start R.45 here. If a later stage is authorised, limit it to route A: record a user-supplied redacted product sheet under the empty schema. Do not open route C, do not download candles, and do not repair the accounting conflict in that stage.

R.45 was not started.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**
