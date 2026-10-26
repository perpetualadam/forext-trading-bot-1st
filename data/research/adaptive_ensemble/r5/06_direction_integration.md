# Direction integration

CODE MODIFIED in R.4 and left in place. R.5 confirmed the live evaluation function calls `direction_action_gate` and does not contain the old `get("direction", "BUY")` fallback.

SYNTHETICALLY TESTED: BUY, SELL, lowercase, spaces, None, blank, whitespace, UNKNOWN, NO_TRADE, and numbers. Invalid values made zero sizing, construction, reservation, and dispatch calls in the gate.

The trading loop function was not executed. `backtest.py` still has a separate fallback and was not changed.
