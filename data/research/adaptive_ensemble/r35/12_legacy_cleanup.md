# Legacy stub-test cleanup

Operational `_quant_stub_vote` now abstains. Tests that expected BUY or SELL were updated to that contract:

- `tests/test_silent_skip_observability.py`
- `tests/test_momentum_m5_dedup_research.py`
- `tests/test_quant_stub_mapping.py`

`tests/test_v2_shadow.py` and `tests/test_decision_quality_engine.py` compare the research wrapper with the operational function. Both now abstain, so the equality still holds.

Three old `evaluate()` tests patched `bot_loop.fetch_ohlcv`. That attribute is no longer on the module. Those tests were retired instead of calling the live candle path. Shared-path fail-closed behaviour stays in the R.34 tests.

`live_path.py`, `reports.py`, and `shadow/fidelity.py` no longer describe the stub or an unverified RL sample as the operational decision. The historical shadow copy in `shadow/original.py` was left unchanged.

`ai_ensemble.py` and `rl_agent.py` were not modified in R.35.
