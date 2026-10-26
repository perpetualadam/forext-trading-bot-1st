# R.81 executive summary

Classification: `R81_RATE_LIMIT_AND_RECOVERY_SAFETY_VERIFIED_OFFLINE`

Production trading remains NO-GO. R.82 was not started.

The R.80 baseline matched. The only operational change is a `live_management_permitted()` check after `acquire_oanda_rest_slot()` and before `api.request` in the OrderCreate and PositionClose sinks. The rate limiter, recovery fencing, permits, and profit-protection parameters were not changed.

Before that check, an authorised child blocked inside the rate-limit slot and a successor startup took the epoch. Releasing the child still sent one OrderCreate, and the close path marked `CLOSE_FULLY_CONFIRMED`. That defect was recorded. After the check, the same interleaving sends nothing, leaves the permit consumed, and does not confirm the close. A current owner still submits each operation once.

Executed after the fix, on Windows and Linux, with separate processes:

- A close owner killed before PositionClose, and killed inside the synthetic request both before and after recorder acceptance, does not get a second close from the successor.
- Repair is refused while an in-progress owner holds the lock. After that owner exits, repair increments the epoch, submits nothing, and the old ambiguous close stays unresolved.
- A confirmed reject can reserve a new close operation. A timeout cannot. A 400-unit fill stays partial. A flat snapshot does not confirm a close.
- An ambiguous entry and an ambiguous close survive a fresh `execute_startup_sequence` and are not resubmitted.

R.80 remained 17 passed, R.79 remained 17 passed, and R.78 remained 21 passed on both platforms. Historical failure totals match R.80. No new genuine behavioural regression was observed.

The final local check still does not make `api.request` atomic. Broker idempotency, power-loss durability, real network execution, PostgreSQL, and data-only mode remain unverified.
