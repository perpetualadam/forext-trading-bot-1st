# Remaining gaps

- A production call with `simulation=False` still returns at the live-permission gate before strategy selection, the AI vote, and the RL veto. Those calls are in the same function and run on the offline continuation. They do not run on the permission-blocked production call.
- The legacy tail's fill classification remains unreachable. It cannot dispatch.
- Missing account data still uses current equity. It is not a new hard block.
- `select_strategy` without the deterministic flag remains the random meta-learner. The six names are not independent signals.
- `RLAgent.decide` has no timeout and no confidence. The timeout case is injected after the real method returns.
- Voter exceptions are swallowed by `AIEnsemble.vote`. No votes fail closed with `allow=False` and a BUY direction that the shared path does not trade.
- Authoritative broker-flat release, PostgreSQL execution, OANDA, `run_bot`, and profitability are NOT_EVALUATED.
