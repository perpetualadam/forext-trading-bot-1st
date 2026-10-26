# R.44 reconciliation with R.27 and R.43

## Still blocked

R.27 classification remains `R27_OANDA_ACCOUNT_CONTRACT_PARTIAL`. R.43 classification remains `R43_FRESH_DATA_CONTRACT_FEASIBILITY_COMPLETED`. Neither verified the account. The same blockers remain: product type, instrument eligibility, stake, pip value, conversion, margin, stops, financing, fees, and transaction currency.

R.43's checklist matches this review. R.44 adds the code locations and the conflicts below. It does not remove a blocker.

## What is now locally verified

- Missing NAV is not copied from balance. `account_core` says so, and R.27 tests covered a balance-only body.
- NAV, balance, and unrealised P&L are separate fields.
- Financing, fee, and transfer kinds fail closed in reconciliation.
- The six default names, the 0.0001 / 0.01 pip convention, and the 5-decimal / 3-decimal price format are what the code does.
- Quant stub, RL, and the six strategy flags remain fail-closed. Hashes match the R.43 preflight.

## Claims that were easy to over-read

- R.27's reconciled example used currency USD, NAV 10000, balance 10010, and fixture id `101-004-1435156-001`. That is a synthetic test, not this account. R.27 said the fixtures were synthetic. Repeating the id as an account fact would be too strong.
- The library examples of margin and closeout fields show that the installed client library has those names. They do not show this account's values. R.27 already kept them out of the risk limits.
- R.43 said the £97.15 figure was in the stage brief and was not read from operational state. R.44 finds the same number as `starting_nav_gbp` in shadow config, labelled simulated and not a broker. It is still not verified NAV and not a spread.
- G.3 `POTENTIALLY_INDEPENDENT` was already retired in R.43. It stays retired.

## Conflicts left visible

- R.26 said the live summary helper substituted balance when NAV was missing, and that the new reconciliation boundary did not. R.27 then changed the helper. Current `account_core` matches the repair. The R.26 sentence is true for the code at R.26 and stale as a description of the helper after R.27. Both reports stay as written.
- `trading.py` converts toward approximate USD. Shadow accounting converts toward GBP with fallback 1.35. The account-summary comment uses GBP as an example. The R.27 fixture used USD. No source selects one currency for this account.
- `Config.TRADING_MODE` defaults to practice. The G.3 candle plan named live `api-fxtrade`. Current mode was not read from the environment.
- `symbols.py` documents spot-FX instrument names. The research intention is GBP spread betting. The account product is unknown, so the names are not confirmed as spread-bet identifiers.

## New implementation assumptions recorded here

- `gbp_usd_fallback` 1.35.
- `BASE_BALANCE` default 10000.
- Paper half-spreads and the un-reopened fill-mid constants.
- `PROFIT_GIVEBACK_PIPS` default 4.
- Unit sizing with no broker minimum.
- Adapter rejection when the instrument quote differs from the account currency.

## External verification still required

Every account-specific row in `08_blockers.md`. Local verification of the code does not close them.
