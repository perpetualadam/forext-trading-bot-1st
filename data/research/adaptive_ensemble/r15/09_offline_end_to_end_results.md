# Offline end to end

The shared path ran the selector, `AIEnsemble.vote`, `RLAgent.decide`, the account gate, sizing, reservation, and one inert adapter call for synthetic BUY and SELL. Permission, inactive strategy, RL veto, invalid vote, missing or unverified account, an open position, historical FILLED, and open reservations produced no adapter call. The iteration did not schedule another cycle. `run_bot` was not entered.
