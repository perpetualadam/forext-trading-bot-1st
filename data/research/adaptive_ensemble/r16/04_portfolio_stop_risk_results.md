# Portfolio stop-risk results

The cap formula remains `open stop risk + candidate stop risk > accepted_equity * MAX_PORTFOLIO_RISK_PCT`. The default percentage is 0.05. It was not changed.

| Case | Accepted | Fallback | Result |
|---|---|---|---|
| C01 / H21 | 5000 | NAV 20000 | blocked `portfolio_risk_cap`; cap equity 5000; no reservation; no adapter call |
| C02 / H22 | 20000 | NAV 5000 | cap equity 20000; not blocked by the cap; one inert request |
| C03 / H23 | 5000 | `current_equity` raises | one inert request |
| C04 / H24 | 5000 | fallback returns NaN | accepted equity stays 5000; one inert request |
| C05 / H25 | 5000 | curve and NAV change during sizing | accepted equity stays 5000 |
| C06 / H26 | 5000 | `Config.BASE_BALANCE` differs | permission uses 5000 |
| C07 / H27 | 5000 | cached NAV 20000 | cap equity stays 5000 |
| C08 / H28 | open position | n/a | existing `position_risk_dollars` result is about 300 |
| C09 / H29 | 5000 plus that open risk | n/a | existing comparison returns true |
| C10 / H30 | breach | n/a | reservation not attempted |
| C11 / H31 | breach | n/a | adapter call count 0 |
| C12 / H32 | passing equity | inactive strategy | still blocked `STRATEGY_INACTIVE` |
| C13–C15 | n/a | n/a | percentage, stop-risk formula, and sizing formula unchanged |

The pound figures are synthetic fixtures. They are not a broker account balance.

R.12 J43 and R.14 J86 previously expected a very large accepted balance to miss the cap because the cap still used fallback equity near `BASE_BALANCE`. Those assertions now require the cap equity to equal the accepted balance. A 1 percent size is inside the 5 percent cap of that same balance, so the fallback no longer vetoes it.
