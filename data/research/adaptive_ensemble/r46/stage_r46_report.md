# STAGE R.46 — OFFLINE v20 GBP SPREAD-BETTING CONTRACT VERIFICATION REPORT

Classification: `R46_V20_GBP_CONTRACT_RECONCILIATION_COMPLETED`

This classification means the user-reported screen facts were reconciled with R.44 and R.45 and the remaining blockers were kept. It does not mean the account contract is fully verified. It does not authorise trading. `ACCOUNT_VERIFIED` is not used.

## Branch, HEAD, and preservation

Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`. Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The working tree was already dirty and those unrelated changes were left in place. R.24–R.45 evidence is present. All six strategies stayed inactive. The quant stub stayed `quant_stub_removed`. RL on an unseen state stayed `UNAVAILABLE`. Research lifecycle code is not imported by `bot_loop.py` or `ai_ensemble.py`. No production source was edited. No account identifier was recorded. No network request was made.

## Redacted account profile

The profile is `USER_REPORTED_ACCOUNT_SCREEN` from the R.46 authorisation. Observation: 21 October 2026, about 17:19 UK local time, which is about 16:19 UTC under British Summer Time. That UTC figure is a calendar conversion, not a broker timestamp.

Displayed: OANDA, Live, v20, spread betting, home currency GBP, balance £97.15, NAV £97.15. Those two amounts are one historical snapshot. They are not available margin, not a current balance, and not a position size. Equality of the two displayed figures does not establish open positions or margin used. OANDA One and MT4 are outside the profile. Retail versus professional was not displayed.

The shadow constant `starting_nav_gbp` is 97.15 under `SIMULATED_SHADOW_NOT_BROKER`. That constant is an `IMPLEMENTATION_ASSUMPTION`. It matches the snapshot amount and does not show that the constant was read from the broker. `Config.BASE_BALANCE` default 10000 is a different assumption.

## Evidence classifications

The screen report sets the target profile. Public v20 formulas stay `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS`. Local USD accounting, the 1.35 shadow fallback, the practice-mode source default, and the spot-FX name comment are `CONFLICTING_EVIDENCE` against that profile. The R.27 summary fixture remains `SYNTHETIC_TEST_ONLY` and is not this account. Its identifier is not reproduced.

No retrieved R.45 source was classified `PUBLICLY_DOCUMENTED_V20_SPREAD_BET`. No recorded sentence both named v20 and stated a spread-betting term without a CFD heading or a mixed product page. The screen report is what joins those two labels.

## v20 and OANDA One

Kept as candidates for this profile, still scope-limited: v20 margin at the current mid; closeout percent equal to half of margin used divided by NAV mid, with full liquidation at 100% or higher; daily financing around 5pm ET; settlement conversion at mid plus or minus 1.0% on v20 and v20 MT4 when the quote is not the home currency.

Excluded from the specification: OANDA One sided margin, the 50% coverage liquidation of the largest losing trade, and OANDA One FX financing that accrues until close.

## Spread betting and CFDs

Spread-betting page statements considered for the product: no ownership of the underlying, a directional wager, profit only beyond the spread, MT5 cannot place a spread bet, marketing hours 22:00 GMT Sunday to 22:00 GMT Friday, and a commission-free marketing sentence. EUR/USD "from 0.6 pips" remains a marketing floor.

Excluded: the 76.6% CFD loss warning, MT5 indicative prices, the Forex CFDs session and 100,000-unit lot, share and ETF CFD commissions, the unrendered retail CFD margin card, and the CFD forex Key Information Document. The guaranteed-stop page says CFDs. The spread-betting page says forex guaranteed stops exist. Both stand. Distance and premium remain unknown.

## Six-instrument matrix

EUR/USD is the only name on the spread-bet marketing page. GBP/USD, AUD/USD, USD/CAD, USD/CHF, and USD/JPY were not named as spread-bet instruments. Eligibility for all six is `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED`. Code pip size is 0.0001, or 0.01 for USD/JPY. Code price format is 5 decimals, or 3 for USD/JPY. Those are local conventions. Minimum size, increment, GBP pip value, pair margin rate, and stop premium are `UNKNOWN` or `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED`. For a GBP account, the adapter returns `exposure_conversion_missing` on every pair, because none is quoted in GBP.

## Stake versus units

Public pages and the order path speak in units. A GBP-per-point stake is not defined. One unit is not treated as one pound per pip. The 10,000-unit example, the 100,000-unit CFD lot, and the 10000 balance default are not an intended trade size. `MAX_POSITION_UNITS` defaults to 0, which the code treats as no clamp. A later GBP risk figure needs the ticket's size unit, the pip distance, the point distance, the stop distance, the minimum and the increment, and the conversion markup. No factor was chosen and no conversion was implemented.

## GBP accounting conflicts

`trading.py` stops at approximate USD. Shadow accounting divides that kind of USD amount by GBP/USD or by 1.35. The public candidate is the 1.0% v20 mid markup, and a financing example uses 0.5%. The fill parser treats `pl` as account currency without proving the field is GBP. Financing stays `UNAVAILABLE`. NAV and balance stay separate fields even though the snapshot showed them equal. No correct GBP P&L is claimed. The conflict was not repaired.

## Risk and margin blockers

The £97.15 snapshot shows why a wrong denomination matters. It was not turned into leverage or a position. The bot has no verified GBP risk limit, no pair margin rate, no applied closeout rule, no verified stop distance, no financing amount, and no confirmed conversion on a fill. Each of those blocks practice and live orders. Fail-closed behaviour is unchanged.

## Minimum account-specific verification

Still required, in order: pair eligibility, the stake-to-units field, minimum and increment, pip and point money value, the conversion markup, the pair margin rate, closeout and NAV field names, stop and guaranteed-stop terms, financing as applied, and the currency of fill `pl`. A redacted EUR/USD ticket can address the size field. Public pages cannot. A read-only API query is designed and not authorised.

## Tests and preservation

The offline suites passed on the first run, including R.10 with 69 passed and 5 skipped. `WinError 5` did not appear. There was no retry. R.28 PostgreSQL scripts were not run.

## Recommended R.47 direction

Do not start R.47 from this stage. If a later stage is authorised, keep it to one redacted EUR/USD ticket or instrument screenshot for the size-field wording, the minimum, the increment, and any pip or point label. Do not request a credential, read the account, download candles, insert public rates into a backtest, or repair the USD path. Leave the R.42 range rule unchanged.

PRODUCTION DEPLOYMENT: NO-GO

PRACTICE ORDERS: NOT AUTHORISED

LIVE TRADING: NOT AUTHORISED

ROLLBACK: NO-GO
