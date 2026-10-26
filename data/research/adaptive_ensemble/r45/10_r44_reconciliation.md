# R.45 reconciliation with R.44 blockers

`ACCOUNT_VERIFIED` is not used. A public page does not prove this account.

| R.44 blocker | Outcome | What was learned |
| --- | --- | --- |
| Product and jurisdiction | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | OANDA Europe Limited publishes a UK spread-betting sub-account and a separate CFD product. FCA retail leverage caps are stated. The user's product, category, and permission are not on the page. |
| Instrument eligibility | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | EUR/USD is named in spread-bet marketing. The other five are not listed there. A CFD "all FX except TRY" row is not spread-bet eligibility. |
| Stake versus units | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | Retrieved pages use units. A CFD FX lot is 100,000 units. No v20 stake-per-point map was found. |
| Minimum and increment | `NOT_FOUND` | Examples use large unit sizes. No minimum or step for these pairs was published in the retrieved text. |
| Pip value in GBP | `NOT_FOUND` | Pip arithmetic in examples uses 0.0001 for EUR pairs. GBP per pip is not defined. USD/JPY pip size was not in the retrieved examples. |
| GBP conversion | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | v20 and v20 MT4 settlement markup is 1.0% of mid when the quote is not the home currency. A financing example uses 0.5%. OANDA One is outside the 1.0% sentence. Home currency is still an account fact. The local USD-versus-GBP code conflict is not resolved. |
| Margin and closeout | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | Retail class caps and two different closeout machines, v20 and OANDA One, are published. The pair's class, the sub-account, and the account rate are not. |
| Stops | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | A normal stop can slip. A GSLO is filled at the level and charged only if triggered. The GSLO page says CFDs. Distance and premium are on the ticket, not in the page. |
| Overnight financing | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | The FX formula, 1% admin fee for other pairs, 5pm ET, and v20 daily versus OANDA One accrue-until-close timing are published. The daily tom-next rate was not taken. |
| Weekend financing | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | FX weekend cost is usually tripled on Wednesday because of T+2, unless a holiday moves it. The cash amount still needs that day's rate and the sub-account rule. |
| Fees and current spread | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | Spread-bet marketing says commission free and "from 0.6 pips" on EUR/USD. MT5 indications are not spread-bet fills. Share-CFD commissions do not apply. No current quote was requested. |
| Transaction currency | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | The charges page says realised P&L is converted into the account home currency and can be seen on a transaction report. The report was not opened. The currency of this account is unknown. |

Public terms that can inform a later specification, after the account facts exist: the unit-based margin formula, the v20 and OANDA One closeout split, the FX financing formula, the Wednesday triple rule, and the 1.0% v20 settlement markup. They cannot be applied until product, sub-account, client category, and home currency are confirmed.
