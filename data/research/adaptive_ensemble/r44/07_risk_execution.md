# R.44 risk and execution dependencies

Synthetic tests show how the code behaves on fixtures. They do not show that the path is safe on this account.

| Safeguard | Local evidence | Depends on an unverified broker term |
| --- | --- | --- |
| Daily loss and drawdown | R.25 and R.26. Limits use snapshot NAV. A missing NAV blocks. | The live NAV, and which currency it is in |
| Exposure cap | R.26 and R.27. Notional uses units and a conversion price. Missing conversion returns `exposure_conversion_missing`. | Quote-to-account conversion and the account currency |
| Margin check | `marginAvailable` is stored. It is not a pre-trade limit. Closeout is not applied. | Margin rate and closeout |
| Stop requirement | Code can send a stop price and chooses bid or ask as the trigger side. Minimum distance is not in the reviewed code. `PROFIT_GIVEBACK_PIPS` defaults to 4. That is a code default. | Broker minimum distance and guaranteed-stop rules |
| Broker-order translation | Units, `BASE_QUOTE` names, and 5-or-3 decimal prices | Whether the spread-bet identifier, stake, and precision match |
| Execution reconciliation | Fill `pl`, price, units, and id. Unresolved order states fail closed. Provenance `live` is rejected. | A real transaction page and its currency |
| Reservation and recovery | R.10–R.24 synthetic suites. An unresolved order must not look flat. | The broker's actual order state names |
| Financing | Explicitly unavailable. A financing transaction kind blocks classification. | The rate, the clock, and the weekend rule |
| Fail-closed stubs | Quant stub removed. RL unseen stays `UNAVAILABLE`. Six strategies inactive. | None of that authorises an order |

R.27 exercised `fetch_account_summary` only with a stubbed request. A balance-only body returns `broker_equity_missing`. The synthetic success case used NAV 10000 and balance 10010 in currency USD, with fixture account id `101-004-1435156-001`. That id and those amounts are `SYNTHETIC_TEST_ONLY`.

Passing those tests does not authorise practice or live trading.
