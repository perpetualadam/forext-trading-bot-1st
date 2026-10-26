# R.56 first live diagnostic

## 1. Overall result

**FAIL**

The reviewed standalone entry point was started once. It exited before any session record was written. No broker request was made. The session is not complete and is not a successful diagnostic.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

## 2. Permit

The permit was not consumed. `real_activation` still contains only `one_session.permit`. Its write time is unchanged from preparation. `one_session.consumed` was not created.

## 3. Summary request

Not attempted. No real diagnostic log was created.

## 4. Pricing request

Not attempted. Pricing is `NOT_SENT` because the session ended before summary.

## 5. HTTP status codes

None received.

## 6. Home currency

Not observed. There is no account summary.

## 7. Usable quotes

None. No pricing response was received.

## 8. Spreads

None.

## 9. Market closure

Not applicable. No quotes were requested.

## 10. Sanitised error

The entry process exited without writing a session record and without consuming the permit. No credential was read by this inspection. No HTTP error code was produced. The console was not given a confirmation or a token by the agent.

## 11. Child processes

No diagnostic worker was still running. No Python process remained. No diagnostic child had been recorded.

## 12. Source gate

`REAL_SESSION_SOURCE_ENABLEMENT = False`.

SHA-256 of `live_session_gate.py` is `ae07d4ca969c8696215510a059e7c5c9e6d66933834b3117080e21207bfeee9a`.

## 13. Consumed marker

No consumed marker exists, because the permit was not consumed. Nothing was deleted or regenerated.

## 14. Orders

No order, position, or account-modification endpoint was attempted. `main.py` was not started.

## 15. Remaining gaps

GBP pip value, home-currency conversion, financing, stake-to-unit mapping, and executable position size remain unverified. No broker evidence was collected.

The diagnostic was not started again.
