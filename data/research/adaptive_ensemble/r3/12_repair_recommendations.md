# Repairs, not started

1. R3-ORDER-01. On AMBIGUOUS_TRANSPORT_OUTCOME, do not call `mark_order_failed_or_cancelled`. Keep the client id and refuse a new entry until a read-only reconcile says the first order is absent. Tests: fake timeout, then a second id must be refused; fake reconcile showing no order, then a new id may be allowed; fake reconcile showing a fill, then no second order. Approval required. No broker in the test.

2. R3-DIRECTION-01. Replace the default `"BUY"` and the fallback assignment with a no-trade return. Tests: the same input matrix, and the loop must not be required if the check is a pure function. Approval required.

3. R3-INACTIVE-01. No production change until a later test can reach the return without granting live permission. One safe design is to split the inactive check into a pure function and call that. Do not patch out the permission gate to force the test.

4. R3-ASYNC-01. Keep the socket barrier. Do not allow all localhost sockets. Prefer synchronous fixtures.

None of these repairs were made in R.3.
