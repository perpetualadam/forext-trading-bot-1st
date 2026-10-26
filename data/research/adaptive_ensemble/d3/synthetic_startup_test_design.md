# Synthetic startup test design

The harness is `tests/test_strategy_activation_defaults.py`.

It does not import `forex_bot.app`. It does not call `lifespan`. It does not import `bot_loop`, `oanda_client`, `database`, or `config`.

It calls the real `initialise_fail_closed`, `operator_set_strategy_active`, `persist_evolve_disable`, and `assert_new_live_exposure_allowed` against the pytest temporary safety file set by `tests/conftest.py`.

Broker and scheduler coverage are empty lists that the harness never appends to. They prove the harness did not call a broker or start a scheduler. They do not prove the real lifespan skips those calls. Those cases are `MODEL_ONLY_NOT_RUNTIME_VERIFIED`.

The real lifespan order was reviewed statically and still reaches `get_connection`, `build_api`, `fetch_account_summary`, reconciliation, and `run_bot` after `initialise_fail_closed`, including when that call preserves a bad file and returns normally.

Temporary paths are asserted to exclude `data/ops` and `v2_shadow`.
