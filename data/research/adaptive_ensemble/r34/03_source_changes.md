# R.34 source changes

`forex_bot/bot_loop.py` and `forex_bot/strategy_meta.py` were not edited. Their hashes match the pre-change record.

| File | Change |
| --- | --- |
| `forex_bot/ai_ensemble.py` | `_quant_stub_vote`, `LocalLLM`, and `ExternalLLMAPI` return an abstention with direction `None`. `quant` mode returns `unsupported_ensemble_mode`. `api` and `hybrid` register external voters only. An empty set, a tie, `HOLD`, a non-finite confidence, or a voter exception cannot become BUY or SELL. |
| `forex_bot/experiment.py` | Mode comments now describe the retired quant path. The mode string is still recognised so the ensemble can reject it. |
| `forex_bot/rl_agent.py` | `decide` returns `UNAVAILABLE` unless `persisted_ok` is already true and the state has one finite non-zero winner. It does not sample a random action and it does not set `persisted_ok`. |
| `forex_bot/session_rules.py` | `volatility_ok` scores one index from a trailing window ending at that index. Fewer than 20 finite ATR values fails closed. The 2x / 0.5 percentile rule is unchanged. |
| `forex_bot/research/ml_prediction.py` | New research-only validator. It is not imported by the production loop. |
| `forex_bot/research/decision_journal.py` | New research-only schema validator. It writes nothing. |

Synthetic harnesses that inject a unique learned Q row now set `persisted_ok` on that test agent. The process-wide agent remains unverified.
