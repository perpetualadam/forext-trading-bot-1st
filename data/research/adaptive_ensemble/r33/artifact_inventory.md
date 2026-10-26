# R.33 artifact inventory

Local files only. No serialized model was loaded.

| Artifact | Role on the reachable path | Present | Hash |
| --- | --- | --- | --- |
| `forex_bot/ai_ensemble.py` `_quant_stub_vote` | Default directional rule when no API voter is constructed | Source | Recorded with the research-code hashes |
| `forex_bot/rl_agent.py` `RLAgent` | Gate | Source, empty memory | No weights |
| `data/ops/rl_q_table.json` | Named production Q-table path | Absent | None |
| `data/research/decision_repair/rl_state.json` | Named research Q-table path | Absent | None |
| Scaler, encoder, feature schema, label file, training config, seed, saved predictions | Would be required for a trained model | Absent | None |
| `data/historical/EUR_USD_M5.csv` | Offline bars for the stub score | Present | `3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091` |

API voter classes exist in source. They are not artifacts, and they were not constructed. `SeqModel` keeps an in-process price list. It has no weight file.

Source hashes after the score, SHA-256:

| File | SHA-256 |
| --- | --- |
| `forex_bot/ai_ensemble.py` | `2893d1a0b7a5ac9aa54407e5a15d6670f8addfd895c339f013cdaab205db0bbc` |
| `forex_bot/rl_agent.py` | `912280b9854208b7359b2e264adfdf5b1b454e88afd7b5b5fc3cc0f635091e4e` |
| `forex_bot/indicators.py` | `64fe62a7e5fd997b7ea3ecc69b0bbc09ce5d0bc8ede18180a8bd16b209c52fe9` |
| `forex_bot/bot_loop.py` | `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` |
