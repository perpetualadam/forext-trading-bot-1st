# R.44 GBP accounting implementation review

No real-account P&L was calculated. No operational balance was read. The shadow default 97.15 is not a result.

| Item | Status | Where | Class | Mismatch |
| --- | --- | --- | --- | --- |
| Stake versus units | Implemented as units only | `units_for_notional`, `broker_signed_units`, `oanda_exec._order_units_for_open` | `LOCALLY_VERIFIED_IMPLEMENTATION` | No GBP-per-point stake. Spot-style units are not shown to equal a spread-bet stake. |
| GBP per point | Missing | No contract field | `UNKNOWN` | Blocks GBP evaluation |
| GBP per pip | Missing | Pip size is a price increment, not a money value | `UNKNOWN` | Blocks GBP evaluation |
| Price movement | Implemented in price units | Bid/ask candles and quote P&L | `LOCALLY_VERIFIED_IMPLEMENTATION` | Not converted by a verified pip value |
| Position direction | Implemented as buy/sell and signed units | `broker_signed_units` | `LOCALLY_VERIFIED_IMPLEMENTATION` | Does not prove spread-bet long/short wording |
| Spread cost | Partial | Historical bid and ask exist. Shadow table and fill-mid constants are estimates. Research protocols keep financing unavailable. | `ASSUMPTION_ONLY` for the tables | File spreads are historical. They are not commission or current quotes. |
| Conversion into GBP | Partial and conflicting | Shadow: USD notion, then divide by GBP_USD or 1.35. `trading.py`: stops at approximate USD. Adapter: `exposure_conversion_missing` when quote currency differs from account currency. | `CONFLICTING_EVIDENCE` | Three local treatments. None is a broker conversion charge. |
| Realised P&L | Partial | `oanda_exec._parse_fill` treats fill `pl` as account-currency P&L. R.27 recorded that. | `LOCALLY_VERIFIED_IMPLEMENTATION` of the parser | The account currency of `pl` is unverified. |
| Unrealised P&L | Partial | Separate field in the adapter. Not copied into NAV. | `LOCALLY_VERIFIED_IMPLEMENTATION` | Not a GBP mark. |
| Financing | Missing as a model. Present as a block. | `FINANCING_STATUS = UNAVAILABLE`. Reconciliation returns `pnl_classification_unresolved` for kind `financing`. | `LOCALLY_VERIFIED_IMPLEMENTATION` of the block | The charge itself is `UNKNOWN`. |
| Margin used | Missing from the cached summary | R.27: fetch omits `marginUsed` so earlier source checks stay intact | `LOCALLY_VERIFIED_IMPLEMENTATION` | Account margin is `UNKNOWN` |
| Available margin | Parsed, not a risk limit | `marginAvailable` on the summary | `LOCALLY_VERIFIED_IMPLEMENTATION` | Not a closeout rule |
| NAV | Implemented as its own field | `account_core`: missing NAV is not taken from balance | `LOCALLY_VERIFIED_IMPLEMENTATION` | Current NAV was not read |
| Balance | Implemented as its own field | Same parser. `Config.BASE_BALANCE` default 10000 is separate. | `LOCALLY_VERIFIED_IMPLEMENTATION` plus `ASSUMPTION_ONLY` for the default | Balance is not NAV and not a spread |
| Margin closeout | Missing from risk checks | Library examples name the fields. R.27 did not use them as limits. | `DOCUMENTED_BUT_ACCOUNT_UNVERIFIED` | Closeout percent is `UNKNOWN` |

The spot-unit formulas in `trading.py` and `shadow/accounting.py` multiply price distance by units. A spread-bet stake can be GBP per point with a different size step. Those formulas are not evidence that the two conventions match.
