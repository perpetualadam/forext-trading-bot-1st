# R.86 Portfolio Reporting Audit

Evidence: source inspection of `portfolio_exposure.py`, `bot_loop.daily_report`, `telegram_control.py`, and `app.py`. The exposure module was not edited. Its hash remains `0949a084722697c80cdda5da8c1b7e69ea47dc19c5f718b1f43668a0bb5ae4b4`.

| Existing figure | What it actually sums |
| --- | --- |
| `approx_gross_usd_notional` | Managed `positions` only, approximate USD |
| `approx_signed_usd_exposure` | Managed book, signed heuristic |
| `exposure_snapshot` | Those two figures plus cap settings |
| `daily_report` | Equity, Sharpe, win rate, drawdown. It calls the cycle portfolio update from managed state |
| Telegram and `app.py` status | `exposure_snapshot()` |
| Entry notional check | Proposed units plus managed book |

Quarantined rows are absent from all of those. Journal remainders are absent. Broker observations are absent. The gross figure can therefore understate a quarantined remainder. It is a managed-book heuristic, not verified broker exposure, and it uses fallback FX rates inside `account_ccy_to_usd`.

The report module does not replace those functions. It adds separate names:

- `managed_units_by_instrument`
- `quarantined_journal_units_by_instrument`
- `broker_observed_units_by_instrument`
- `unknown_exposure_count`
- `exposure_completeness`
- `cross_instrument_raw_unit_total`, always null

Directions are kept apart. EUR_USD units and USD_JPY units are not added. No monetary NAV is calculated. The trading cycle does not call the new function, so sizing, signals, and the daily report keep their previous behaviour.
