# R.34 removal plan

Written before the source edits. Historical R.24–R.33 files stay unchanged.

## Operational removals

- `forex_bot/ai_ensemble.py`: `_quant_stub_vote` stops returning BUY or SELL. `LocalLLM` is not registered for `quant`, `api`, or `hybrid`. `AI_DISABLE_STUB` no longer inserts or removes a heuristic. `ENSEMBLE_MODE=quant` returns an unavailable result. An empty voter list abstains with direction `None`.
- `forex_bot/rl_agent.py`: `decide` returns `UNAVAILABLE` unless `persisted_ok` is true and the requested state has one finite, non-zero winning action. It does not sample a random action and it does not mark an empty table as valid.
- `forex_bot/session_rules.py`: `volatility_ok` scores one timestamp from a trailing window that ends at that timestamp. Fewer than 20 usable ATR values fails closed.

## Left unchanged

- `forex_bot/bot_loop.py`, strategy flags, sizing, reservation, and order routing.
- `forex_bot/shadow/signals.py` moving-average strategy rules.
- R.33 evaluation output and the historical stub scorer.
- Research copies under `forex_bot/decision_quality/` and `forex_bot/shadow/original.py`. They are not the operational registration path. Callers that still import the retired function receive an abstention.

## New research-only modules

- `forex_bot/research/ml_prediction.py`
- `forex_bot/research/decision_journal.py`

Neither module is imported by the production loop or registered as a voter.
