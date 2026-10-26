# Shared decision refactor

CODE MODIFIED: `forex_bot/bot_loop.py` only among application modules.

The shared function now calls the existing selector, the existing `AIEnsemble.vote` wrapper, and the existing `RLAgent.decide` method when the scenario reaches those stages. Permission, position, exposure, and broker-exit gates stay before them. Direction is still canonical BUY or SELL. Sizing, risk, and reservation are unchanged. A fake broker is used only when `simulation` is true and the live-order gate is already blocking.

`production_execution_adapter` is the single function that calls `execute_oanda_market_open`. The shared path names that function and does not call it. A non-simulation decision returns `production_execution_adapter_withheld` if it ever reached the adapter boundary. Tests stop earlier, at the live-permission gate.

Production dependencies set `invoke_selector`, `invoke_vote`, and `invoke_rl`, and carry the process RL agent. With `simulation=False` the permission gate still returns before those calls. That preserves the protective order. The offline driver sets `simulation=True` only inside tests so the same function can continue to the fake broker.

The legacy tail now returns before any broker call. Its later fill-classification code remains in source and is unreachable. It was not deleted because the production OANDA exception classification has no offline parity evidence.
