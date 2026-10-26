# Inactive strategy integration

CODE MODIFIED. `continue_entry_after_strategy_gate` is now the check `_evaluate_impl` uses before indicators and sizing.

SYNTHETICALLY TESTED with spies:

- Inactive known strategy: sizing 0, construction 0, client ids 0, dispatch 0.
- Unknown strategy name: the same zeros.
- All six default strategies are inactive.

`evaluate` and `run_bot` were not called. The test called the same gate the loop calls. Live permission was not granted and no strategy was activated.
