# Offline end to end

The shared path ran the actual selector, `AIEnsemble.vote`, and `RLAgent.decide`.

Synthetic BUY and SELL at accepted equity 5000 each recorded one inert adapter request. Sizing equity and portfolio-cap equity were both 5000.

A cap breach, a missing account, an unverified account, a stale harness timestamp, an inactive strategy, an RL veto, an invalid direction, an open position, a historical FILLED hold, and PENDING, PARTIAL, and UNRESOLVED reservations produced no adapter call.

A zero stop blocked before reservation. A persistence failure blocked before the adapter. Rejection, timeout, ambiguity, a partial fill, a malformed response, and a position-recording failure kept the existing outcome rules. A duplicate client id was refused. The iteration did not schedule another cycle. Real broker requests were 0.
