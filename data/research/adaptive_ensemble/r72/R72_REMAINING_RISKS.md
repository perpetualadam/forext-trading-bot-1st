# R.72 Remaining Risks

Still open, and not claimed fixed:

| Finding | Status |
| --- | --- |
| R66-03 `broker_sl_tp_hit` returns false | Open. The wrapper still returns false so a pending stop cannot become a close. |
| R66-05 local prices are not broker protection | The new reader treats them as non-evidence. The old reconcile field parser still stores a price only. That parser was not changed. |
| R66-07 account-currency sizing | Open. Sizing was not modified. |
| R66-10 local removal without matched close units | Open. Evidence does not delete, and the old close path can still drop a permitted row. |
| R66-11 ambiguous close identity | Open. No close idempotency key was added. |
| R66-16 management and reconciliation synchronisation | Open. Evidence publication and the reconcile report are separate. |

Additional limits of this stage:

- Exit attribution is never confirmed here. A filling transaction id on the trade document is not a retrieved transaction.
- Confirmed absence depends on OANDA including an explicit null `stopLossOrder` or `takeProfitOrder`. If the live API omits the key when no order exists, absence stays unknown. That is intentional.
- The evidence generation counter does not survive a restart and is shared across symbols.
- Linux did not import `oandapyV20`, so the operational module did not run there.
- No practice or live TradeDetails call was made.
- PostgreSQL was not connected.
- Production entry remains blocked. That is not a profitability result.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

`POSTGRESQL_INTEGRATION_NOT_TESTED`

`LINUX_INTEGRATION_NOT_VERIFIED`
