# R.66 Strategy-evidence audit

This audit did not calculate performance and did not invent trades. Profitability cannot be assessed from the work in this stage.

## What was not used as evidence

- No backtest was executed. `forex_bot/backtest.py` exists and is not imported by `app.py` or `bot_loop.py`. Its results, if any were produced in the past, were not reloaded as proof.
- No PostgreSQL trade table was queried.
- No broker transaction history was requested.
- `.env` and credential files were not opened.
- Synthetic unit examples in the risk audit are formula checks. They are not a track record.
- Research reports under `data/research/adaptive_ensemble/` from earlier stages are not a live trading record. R.56–R.65 are diagnostic and containment work. They do not authorise a performance claim.
- Shadow signals and `v2_shadow` observations are hypothetical or recorded market rows. The shadow module says they are not live AI decisions (`shadow/signals.py` 1–6).

## Metrics

| Metric | Status |
| --- | --- |
| Net return, drawdown, profit factor, expectancy, win rate, average win, average loss, payoff, Sharpe, Sortino | `NOT_VERIFIED`. Not computed |
| Trade frequency, exposure, holding time | `NOT_VERIFIED` |
| Slippage and spread in production fills | `NOT_VERIFIED`. No fills were read. Paper simulation has a fixed spread model in `apply_execution_costs` |
| Swap and financing | No financing term was found on the order or close path that this audit traced. Absence on that path is source review of those modules, not a proof that the broker charges zero |
| Walk-forward, out-of-sample, Monte Carlo, bootstrap | Not executed and not accepted from unread historical files |
| By pair, by regime, long versus short | `NOT_VERIFIED` |

## Bias checklist for the code that would trade if the entry tail were enabled

These are properties of the source, not measured backtest defects.

| Topic | Source observation |
| --- | --- |
| Look-ahead | Indicator windows end at the current row. `fetch_ohlcv` drops `complete == false`. A missing `complete` key is treated as true (`R66-13`) |
| Repainting | `compute_indicators` does not revise stored historical values. RAM sequence history changes with restarts |
| Data leakage | The live voter would see the same bar it decides on. That is a closed-bar decision only when `complete` is trustworthy. No label from the future is joined in `compute_indicators` |
| In-sample optimisation | `select_strategy` can weight by in-memory Sharpe after 10 meta samples (`strategy_meta.py` 87–92). The sample is process-local. This audit found no locked out-of-sample parameter set wired into `run_bot` |
| Unrealistic fills | Paper path can fill at mid or at a spread-plus-slippage model (`trading.py` 243–275). Broker path would use the fill transaction. The broker path is not reached |
| Costs | Paper spread is a table or one pip, times multipliers (`trading.py` 101–109 and 255–268). Financing is not in that function |
| Survivorship | The default symbol list is six pairs (`symbols.py` 12–18). It is not a historical membership list of a universe |

`analytics.sharpe`, drawdown, and win rate are called from `run_bot` on whatever `analytics` has logged in the process (`bot_loop.py` 4413–4420). An empty process has no closed trades to summarise. Those calls are not a historical study.

## Conclusion

`PROFITABILITY_NOT_ASSESSED`. There is not enough evidence in this audit to say the strategy is profitable, unprofitable, or ready for evaluation. The operational cycle does not currently submit the strategy's entries, so a future performance test would be a test of management and reconciliation until the entry producer is deliberately changed and reviewed.
