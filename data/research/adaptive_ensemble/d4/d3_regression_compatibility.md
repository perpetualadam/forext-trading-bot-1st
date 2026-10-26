# D.3 regression compatibility

`strategy_meta.py` was not edited. Its hash still matches the D.3 result.

`tests/test_strategy_activation_defaults.py` was run again: the 35 tests passed.

Fresh strategies still start inactive. Assigning `"false"` or `1` does not activate. All six names are covered. A protected file leaves them inactive. The operator workflow still requires confirmation.

`bot_loop.py` was not modified. Its skip of the `authorised_for_live` check when safety state is invalid remains a static residual. The inactive check is still first, and startup now aborts before `run_bot` when the file is protected. That abort was not executed as a running loop.
