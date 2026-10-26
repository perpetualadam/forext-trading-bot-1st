# R.71 Risk and Sizing Audit

The formulas were not changed. They were called directly under the R.69 isolation harness. The entry call site remains blocked.

## Formula

`position_sizing` (`trading.py` 278–325) uses `equity * risk_pct / risk_per_unit` unless `POSITION_NOTIONAL_PCT_OF_NAV` is positive, in which case it sizes by face value. Default risk is 1 percent, capped by `POSITION_RISK_PCT_MAX` at 1 percent. Margin and leverage are not modelled. The comment says OANDA may reject the order. Minimum size returned by the risk path is 1 unit. `MAX_POSITION_UNITS` can clamp later.

`stop_risk_account_ccy` (163–172):

- If the symbol starts with `USD_`, risk is `(stop_distance / mid) * units`.
- Otherwise risk is `stop_distance * units`.

The second branch treats quote-currency loss as account currency. For EUR_USD that quote is USD. It is not converted to GBP.

`account_ccy_to_usd` (`portfolio_exposure.py` 60–72) defaults a blank `broker_currency()` to USD. A GBP balance would use `GBP_USD` mid or the fallback 1.35. `broker_currency` is set from an account summary (`state.py` 51–63). This audit did not fetch an account. The operational design therefore supports a non-USD currency field and still prices non-USD-base stop risk as quote currency.

## Worked synthetic examples

Environment forced in the test: notional percent 0, risk 1 percent, risk cap 1 percent, ATR stops off.

| Case | Inputs | Result |
| --- | --- | --- |
| EUR_USD fallback distances | 20 pips, reward 2 | Stop 0.0020, target 0.0040 |
| USD_JPY fallback distances | 20 pips, reward 2 | Stop 0.20, target 0.40 |
| EUR_USD stop risk | 50,000 units, 0.0020 distance | 100.0 quote currency, which is USD |
| EUR_USD size | Equity 10,000, risk 1 percent, stop 0.0020 | 50,000 units |

If that 10,000 were GBP, the formula still divides 100 by 0.002 and still reports 100 of quote risk. It does not multiply or divide by a GBPUSD rate inside `stop_risk_account_ccy`. That is the USD-account assumption. It is not a claim about any live account.

## Other risk controls

- `MAX_PORTFOLIO_RISK_PCT` defaults to 0.05 (`trading.py` 211–214). The check runs on the blocked entry tail.
- Gross notional uses a USD heuristic (`portfolio_exposure.py` 103–116). USD-quote pairs use units times price. USD-base pairs use units. Other crosses use the quote-style product. Pending orders and margin are excluded (175–176).
- Correlation is only the rough signed USD exposure (127–144). There is no pair-correlation matrix on the order path.
- Existing exposure is the in-memory book only.

R66-07 remains open.
