# RL veto

ACTUAL RL VETO EXECUTED.

`RLAgent.decide` is the production veto. It returns BUY, SELL, SKIP, or UNAVAILABLE. It does not return a confidence. SKIP blocks. A side that differs from the AI direction blocks. UNAVAILABLE blocks when `DECISION_REPAIR_RL_REQUIRE_STATE` is on and the agent has not persisted. The veto runs before reservation and before the fake broker.

The production agent is epsilon-greedy. Offline tests use a separate `RLAgent(epsilon=0)` whose Q table has one best action, or a probe that calls `super().decide` and then returns a controlled bad value. The process agent's Q table and epsilon were unchanged after the tests.

The real method has no timeout. The timeout test calls `decide` and then applies a test-injected timeout outcome. No order follows.
