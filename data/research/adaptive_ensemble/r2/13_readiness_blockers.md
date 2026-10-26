# Remaining blockers after R.2

## Critical safety

- An uncertain broker result is caught as a failed order and the reservation is marked failed (`bot_loop.py` 1527-1532). The next cycle creates a new client id. That can send a second order after a timeout. This was read from source. It was not executed.
- If the AI vote is allowed but the direction is blank, the loop forces BUY (`bot_loop.py` 1177-1178).
- The inactive-strategy return before sizing is in the source and was not executed in a test.

## Strategy evidence

- The six names do not choose buy or sell on the live path.
- Shadow rules do not place live orders.
- The session recount still finds 27 complete common sessions. The bar remains 40.
- No profitability numbers were calculated.

## Broker readiness

- Practice orders are not authorised.
- Spread-bet instrument names were not checked with OANDA.
- Financing is still unmodelled.
- The async paper-order tests could not run under the socket barrier on Windows.

## Optional infrastructure

- Docker, image pins, and registry work do not close the decision-path or session gap.
