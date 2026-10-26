# Findings

## R3-ORDER-01

Plain English: after an uncertain send, the code marks that reservation failed and will accept a different order id. The first broker result is still unknown, so the second id can become a second trade.

File: `forex_bot/orders.py`, `mark_order_failed_or_cancelled` lines 164-170, and `try_begin_order_submission` lines 93-132. The loop that would call the mark function is `forex_bot/bot_loop.py` lines 1527-1532. Classification of the timeout is `forex_bot/oanda_exec.py` lines 289-316.

Evidence: SYNTHETICALLY REPRODUCED for the functions. The loop's except block was not entered. SOURCE-TRACED for the fact that the except block calls the mark function.

Observed: timeout class is `AMBIGUOUS_TRANSPORT_OUTCOME`. After the mark, the same id was refused. A newly generated id was reserved. No broker function ran.

Safe behaviour: do not reserve a new id until the first outcome is known.

Severity: HIGH if live sending is later turned on. It is latent now. Live permission is blocked and the strategies are off, so this path is not currently reachable for a real order.

Mitigation: same id cannot be reused while it remains in memory. Live authorisation is fail-closed. Neither one checks the unknown order with the broker.

Repair later: on an ambiguous result, keep the reservation and block new entries for that symbol until a read-only reconcile. Do not mark it cancelled. That repair is not part of R.3.

## R3-DIRECTION-01

Plain English: a missing or unrecognised direction becomes BUY.

File: `forex_bot/bot_loop.py` lines 1176-1178.

Evidence: SYNTHETICALLY REPRODUCED on those three lines. The surrounding function was not called.

Observed: missing key, None, blank, spaces, NO_TRADE, UNKNOWN, 0, and 1 became BUY. BUY and SELL were preserved, including lowercase.

Safe behaviour: an absent or unrecognised direction must not become an order.

Severity: HIGH only after the earlier gates are open: live permission allowed, a strategy active and authorised, and the AI vote already allowing a trade. Those gates were not opened. A vote with allow false returns earlier and never reaches this line.

Repair later: if the direction is not BUY or SELL, return with no trade. Do not default the missing key to BUY.

## R3-INACTIVE-01

Plain English: an inactive name is supposed to stop the loop before sizing. That line was not run. The selector, which was run, can still return an inactive name when the hybrid switch is on.

File: `forex_bot/bot_loop.py` lines 1076-1084 and `forex_bot/strategy_meta.py` `allocate_scoped` lines 115-123.

Evidence: selector SYNTHETICALLY REPRODUCED (`trend` selected while inactive). The early return is SOURCE-TRACED and NOT_EVALUATED at runtime.

Severity: INFORMATIONAL as a coverage gap. It is not a demonstrated bypass. The live-permission check is earlier, and the inactive check is still present in the source.

## R3-ASYNC-01

Plain English: the R.2 async tests failed because the Windows event loop needs a local socket, and the barrier correctly refused it.

Severity: INFORMATIONAL. The async tests were not repeated. Synchronous fixtures covered the order and direction questions.
