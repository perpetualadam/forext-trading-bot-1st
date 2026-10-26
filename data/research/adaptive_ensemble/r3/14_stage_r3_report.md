# STAGE R.3 — OFFLINE TRADING-SAFETY BUG INVESTIGATION REPORT

## 1. Executive summary

- Overall classification: `R3_OFFLINE_BUGS_REPRODUCED`
- Gate A: PASS. Hashes matched and the output folder was empty.
- Gate B: PASS. The timeout path was traced. The loop was not entered.
- Gate C: PASS as an investigation. Fake order results were run. The unsafe new-id path was reproduced.
- Gate D: PASS as an investigation. The three direction lines were run in isolation. Invalid values became BUY.
- Gate E: the setter and the selector were run. The loop's early return was not run.
- Gate F: async tests were not run. `ASYNC_ISOLATION_NOT_PROVEN`.
- Gate G: PASS. The socket barrier held.
- Gate H: PASS. Four findings recorded.
- Gate I: PASS. Protected files still match.
- Synthetic order cases: 11. Safe results: 7. Unsafe results: 3. Not evaluated: 1.
- Direction inputs: 12. Preserved correctly: 4. Became BUY when they should not: 8.
- Bugs reproduced: uncertain-order new id; blank direction becomes BUY.
- Not reproduced: an inactive strategy reaching sizing. That line was not executed.
- Production modified: no. Network requests: 0. Broker requests: 0.
- Next action: do not repair yet. A later approved stage can change the two reproduced lines and add tests. Not started.

## 2. Safety and scope

No broker, Telegram, Discord, DNS, or download. One import-time IPv6 probe inside urllib3 was refused before an operating-system socket existed. The application and the trading loop were not started. Live permission was not granted. Strategies were left inactive. The probe strategy used to test the setter was turned back off. No package install, Docker, or git change.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec`, branch `main`. All ten protected hashes matched before and after. The working tree was already dirty and was not cleaned.

## 4. Uncertain-order source trace

A client id is generated, then reserved. A timeout is classified as ambiguous, which means the broker result is unknown. The loop's error handler treats that exception as a failed order and marks the reservation cancelled. The same id cannot be reused while it remains in memory. The next generated id is different, and the reserve function accepts it. Nothing asks the broker about the first order first.

## 5. Synthetic order results

| Case | Observed | Safety result |
|---|---|---|
| C01 fake fill | FILLED | PASS |
| C02 fake reject | REJECTED | PASS |
| C03 fake cancel | CANCELLED | PASS |
| C04 timeout | AMBIGUOUS_TRANSPORT_OUTCOME | PASS for classification |
| C05 connection reset | AMBIGUOUS_TRANSPORT_OUTCOME | PASS for classification |
| C06 incomplete body | MALFORMED_RESPONSE | PASS |
| C07 same id twice | second reserve false | PASS. Same id is blocked in memory. |
| C08 new id after the uncertain mark | new id reserved | FAIL. Bug reproduced. |
| C09 memory cleared | new id reserved | FAIL. Stand-in for a restart. The database query was not run. |
| C10 broker reconcile | not called | NOT_EVALUATED. No such call is on this path. |
| C11 no reconcile result | new id still reserved | FAIL. Same bug as C08. |

No broker function was reached. `execute_oanda_market_open` was not called.

## 6. Blank-direction source trace

`bot_loop.py` lines 1176-1178 default a missing direction to BUY, then replace anything that is not BUY or SELL with BUY. The rest of the loop was not run. This line sits behind live permission, an active strategy, and an allowing AI vote.

## 7. Direction input matrix

| Input | Result |
|---|---|
| missing key | BUY |
| None | BUY |
| empty string | BUY |
| spaces | BUY |
| BUY / buy | BUY |
| SELL / sell | SELL |
| NO_TRADE | BUY |
| UNKNOWN | BUY |
| 0 | BUY |
| 1 | BUY |

## 8. Inactive-strategy source trace

The return before sizing is `bot_loop.py` lines 1076-1084. It is after the live-permission check. It was not executed, because reaching it would mean getting past that permission check. The permission check was not switched off.

## 9. Inactive-strategy fixture results

All six names defaulted inactive. False, None, `"true"`, and `1` stayed inactive. Boolean True is the only value that turned the probe on, and it was turned off again.

With the hybrid switch on and every name inactive, the selector returned `trend`, which was inactive. Sizing calls: 0. Order calls: 0. Broker calls: 0. Those zeros are because the loop was not entered, not because the return line was watched.

With the hybrid switch off, the selector returned no name.

## 10. Windows asyncio isolation

The Windows proactor loop needs a self-pipe, and that pipe is created with an AF_INET socket. Allowing that family would loosen the barrier too far. The async tests were not repeated. Synchronous fixtures were enough for the order and direction questions.

## 11. Confirmed bugs

R3-ORDER-01 and R3-DIRECTION-01. Both are latent while live permission is blocked and strategies are inactive. Both can matter if that permission is later granted.

## 12. Unverified suspected bugs

The inactive-strategy return itself was not executed. It is still present in the source. It is not a demonstrated bypass.

A real restart against the database was not performed. The source query reloads only PENDING and PARTIAL, so a row marked CANCELLED would not block a new id. That query was not run.

## 13. Existing safety controls

Live-order permission fails closed. Strategies default off. The same client id is refused in memory. An AI vote with allow false returns before the direction coercion. None of these controls reconcile an unknown broker order, and none of them stop the direction fallback once that line is reached.

## 14. Recommended repairs

Do not mark an ambiguous send as cancelled. Block a new id until a read-only check. Do not default a missing direction to BUY. Do not open AF_INET to make the old async tests pass. No repair was made.

## 15. Next three priorities

1. Approve a repair for the ambiguous-order reservation, with fake timeout tests and no broker.
2. Approve a repair so an invalid direction is no trade, with the same input matrix.
3. Leave the inactive-loop line untested until it can be reached without granting live permission.

## 16. Recommended next stage

A repair stage, only after a new approval. It should change only those two behaviours and add offline tests. It should not enable strategies, contact OANDA, or continue Docker work. It is not started.

## 17. Final integrity

Protected hashes match. Extra source hashes match. Network attempts that left the machine: none. Broker calls: 0. Writes stayed under `data/research/adaptive_ensemble/r3`.

## 18. Final classification

`R3_OFFLINE_BUGS_REPRODUCED`

## 19. Hard stop

PRODUCTION DEPLOYMENT: NO-GO.  
PRACTICE-ACCOUNT ORDERS: NOT AUTHORISED.  
LIVE TRADING: NOT AUTHORISED.  
ROLLBACK: NO-GO.
