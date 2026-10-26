# R.44 approved sources and files left unopened

Reviewed:

- `data/research/adaptive_ensemble/r26/stage_r26_report.md`
- `data/research/adaptive_ensemble/r27/stage_r27_report.md`
- `data/research/adaptive_ensemble/r43/06_contract_checklist.md`, `12_ranked_options.md`, and `stage_r43_report.md`
- `data/research/adaptive_ensemble/g3/request_plan.json` as already recorded in R.43. Raw G.3 response pages were not reopened.
- Source: `forex_bot/symbols.py`, `forex_bot/config.py`, `forex_bot/oanda_client.py`, `forex_bot/oanda_account_adapter.py`, `forex_bot/oanda_exec.py`, `forex_bot/trading.py`, `forex_bot/entry_geometry.py`, `forex_bot/account_reconciliation.py`, `forex_bot/shadow/accounting.py`, `forex_bot/shadow/config.py`, `forex_bot/shadow/cost_model.py`, `forex_bot/research/learning/timeframes.py`

`config.py` was read as source. It was not executed, and `.env` was not opened. The preflight stubbed `dotenv` before importing strategy and ensemble modules.

Left unopened because they may hold operational or account material:

- `.env` and any credential file
- `data/ops`
- `data/research/v2_shadow`
- private statements, confirmations, and account documents
- G.3 raw candle pages

No drive-wide search was run. No broker host was contacted.
