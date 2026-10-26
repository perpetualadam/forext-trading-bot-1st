# R.66 Risk and position-sizing audit

Source review only. No account was read. Account currency, NAV, and `FOREX_SYMBOLS` in the environment are `NOT_VERIFIED`. Formulas below are the source. They are not a statement of what a running process would print.

The sizing functions are not on the current `run_bot` entry path. `position_sizing` is called from the unreachable `_evaluate_impl` tail (`bot_loop.py` 1428–1429) and from `evaluate_one_instrument_iteration` only after the function has required `simulation` (`bot_loop.py` 3323–3328, then later 3793–3804). A production cycle does not size a new order.

## Two different size definitions

`position_sizing` (`trading.py` 278–325) branches:

1. If `POSITION_NOTIONAL_PCT_OF_NAV` is greater than 0, units come from `units_for_account_notional`. That targets face value equal to `equity * that fraction`. It is not cash at risk to the stop. The default of the environment variable is 0, so this branch is off unless set.
2. Otherwise units are `(equity * risk_pct) / risk_per_unit`, where `risk_per_unit` is the account-currency loss of a one-unit position if the stop distance is realised. Default `POSITION_RISK_PCT` is 0.01. `POSITION_RISK_PCT_MAX` defaults to 0.01 and caps the fraction. This is cash at risk to the stop, not notional.

The unreachable tail then, only when notional mode is off, multiplies units by `portfolio.get_weight(symbol) * ai confidence` (`bot_loop.py` 1430–1431). The shared-function sizer does not apply that extra scale. The two call sites are not equivalent. Neither runs on the current production cycle.

`cap_position_units` applies `MAX_POSITION_UNITS` when that value is greater than 0. Default 0 means no cap (`trading.py` 230–235).

Broker margin, leverage, and minimum trade size are not applied in `position_sizing`. The docstring says OANDA may reject an oversized order (`trading.py` 289–290). `execution_risk` records `margin_evidence` as not implemented on the shared decision (`bot_loop.py` 3701–3703).

Negative equity is clamped to 0 and returns 0 units. A zero stop distance returns 0. The function then applies `max(units, 1.0)` on the risk-at-stop branch (`trading.py` 325`). A computed size between 0 and 1 becomes 1. That can make the actual stop risk larger than `equity * risk_pct` for a tiny account. The notional branch in the tail floors with `math.floor` and skips when the result is below 1 (`bot_loop.py` 1433–1442). The shared function blocks `units <= 0` but does not apply that floor.

`MIN_STOP_DISTANCE_PRICE`, when set, widens the distance used in the denominator (`trading.py` 316–318`). A wider denominator reduces units. If the order later uses a tighter stop than this floor, realised risk is below the target. If the order uses the same widened stop, risk stays near the target. The floor does not increase units.

## Worked source formulas for a USD account

These are synthetic. They are not trades. `stop_risk_account_ccy` (`trading.py` 163–172): USD-base names (`USD_JPY`, `USD_CAD`, `USD_CHF`, and any other `USD_*`) use `(stop_distance / mid) * units`. Other names use `stop_distance * units`.

Assume mid prices EUR_USD 1.1000, GBP_USD 1.3000, USD_JPY 150.00, AUD_USD 0.6500, USD_CAD 1.3500, USD_CHF 0.9000, equity 10_000, risk fraction 0.01 so risk budget is 100, and a 20-pip fallback stop (`SL_FALLBACK_PIPS` 20, pip 0.0001 or 0.01 for JPY).

| Pair | Stop distance | Risk per unit | Units for 100 of risk | Meaning of the unit risk |
| --- | --- | --- | --- | --- |
| EUR_USD | 0.0020 | 0.0020 USD | 50_000 | Quote is USD. Correct for a USD account |
| GBP_USD | 0.0020 | 0.0020 USD | 50_000 | Quote is USD. Correct for a USD account |
| AUD_USD | 0.0020 | 0.0020 USD | 50_000 | Quote is USD. Correct for a USD account |
| USD_JPY | 0.20 | 0.20/150 = 0.001333 USD | 75_000 | Quote JPY divided by mid. Correct for a USD account |
| USD_CAD | 0.0020 | 0.0020/1.35 USD | 67_500 | Quote CAD divided by mid. Correct for a USD account |
| USD_CHF | 0.0020 | 0.0020/0.90 USD | 45_000 | Quote CHF divided by mid. Correct for a USD account |

`units_for_account_notional` (`portfolio_exposure.py` 75–84) for a 2% face-value target on 10_000 (200 account units, treated as USD when the account currency is USD):

- EUR_USD at 1.10 → `200/1.10` ≈ 181.82 units. That is about 200 USD of quote notional, not 200 USD of stop risk.
- USD_JPY → 200 units. The function treats `USD_*` units as already USD notional.

A 2% notional target and a 1% stop-risk target are different orders of magnitude on these prices. The code does not convert one into the other. Default configuration uses the stop-risk branch.

## Where the USD assumption fails

`quote_pnl_to_account_ccy` and `stop_risk_account_ccy` do not take an account currency. They return a USD approximation:

- `*_USD` quote pairs return quote P&L unchanged.
- `USD_*` pairs divide by mid.
- Any other name, including `EUR_GBP` or `EUR_JPY`, returns quote P&L unchanged and therefore treats GBP or JPY as if it were USD (`trading.py` 148–161).

`account_ccy_to_usd` (`portfolio_exposure.py` 60–72`) converts a NAV amount using `last_mid("{CCY}_USD")` or `_CCY_USD_FALLBACK`. The fallback map includes `"GBP": 1.35`, `"EUR": 1.17`, `"JPY": 0.0067`, and other constants. Those constants are not a verified GBP spread-bet model and are not read from the broker. They apply only when the account currency is not USD and a live mid is missing. This audit did not observe a mid or an account currency.

If the account currency is GBP, the stop-risk sizer still treats `risk_per_unit` as the same currency as `balance`. A USD quote loss would be sized as if it were GBP. That is a dimensional error. It is latent on the current cycle because sizing is not reached. Account currency remains `NOT_VERIFIED`. See `R66-07`.

`execution_risk._exposure_notional` adds `abs(units) * entry` for every symbol (`execution_risk.py` 192–201). For USD_JPY, OANDA units are USD, and multiplying by 150 counts the position about 150 times in a USD book. The shared function's gross cap uses `portfolio_exposure` for the proposal (`bot_loop.py` 3860–3889) and can also form `abs(units) * price` as `proposed` before the cap helper (`bot_loop.py` 3861). That `proposed` path is inside the simulation-only portion. It is not the production cycle. See `R66-08`.

## Portfolio controls that exist in source

| Control | Default | When it runs |
| --- | --- | --- |
| `MAX_PORTFOLIO_RISK_PCT` | 0.05 of equity, sum of stop-risk of in-memory positions | Unreachable entry tail and shared function after simulation |
| `MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV` | Inherits `POSITION_NOTIONAL_PCT_OF_NAV` when unset. That default is 0, and `configured_max_gross_usd` then uses `MAX_GROSS_USD_NOTIONAL`, default 0, which turns the check off | Same unreachable/simulation sites |
| `max_same_usd_direction_positions` | Environment. The guard compares open locals | Same sites |
| Daily loss and drawdown in `execution_risk.entry_risk_block` | Requires configured fractions and an attested state file. Missing baseline fails closed | Isolated simulation context only |
| `DECISION_REPAIR_ACCOUNT_RISK` | Off | `pre_trade_entry_blocked_reason` only when the flag is on |
| Maximum simultaneous positions | One local position per symbol via `get_position`. No separate book-wide count on the active path | Active as "do not open another local row", and the open itself is not reached |
| Weekend flatten | Session rule | Active management of an existing local position |
| Correlation | USD-direction bucket only. No general correlation matrix | Unreachable entry sites |

Open risk is summed from the RAM book (`trading.py` 198–201). A broker position that was not imported is invisible to that sum. A restarted process starts with an empty RAM book unless reconciliation imports.

Rounding: risk-at-stop units are a binary float. The notional tail floors to an integer. Neither path uses broker `tradeUnitsPrecision` or `minimumTradeSize`. Those fields are not read on this path.

Retry: the current cycle does not submit a new order, so a rejection cannot resize and retry. The simulation shared function holds exposure on timeout and does not submit a second broker order.

## Active risk on the cycle that does run

Management does not re-check NAV, margin, or the portfolio stop-risk cap before a protective close. Closing reduces exposure. The financial risk on that path is closing a position the operator did not intend the process to own, or leaving a broker position without a broker stop. Those are execution and reconciliation findings `R66-03`, `R66-04`, and `R66-05`, not sizing findings.
