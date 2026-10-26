# R.66 Signal-generation audit

Evidence class for this file is source review. No market data was fetched and no indicator function was executed, because importing `forex_bot` loads `.env` through `forex_bot.config`.

## What can emit a direction today

The production cycle does not generate an order direction.

`run_bot` → `evaluate` (no injected dependencies) → `_evaluate_impl`. When no local position is open, the next call is `dispatch_production_iteration` with `simulation=False` (`_production_iteration_dependencies`, `bot_loop.py` 4370–4388). `evaluate_one_instrument_iteration` returns at the permission phase (`bot_loop.py` 3321–3328) before strategy selection, indicator use for a decision, the AI vote, and the RL gate.

`_evaluate_impl` then requires status `continue_existing_production_broker` (`bot_loop.py` 1125–1134). That status is not assigned anywhere in `bot_loop.py`. The strategy, vote, and RL block from line 1174 onward is unreachable from `run_bot`.

So the chain `Market Data → Feature Calculation → Strategy Decision → Trade Candidate` is implemented in source and is not entered by the operational cycle.

## Market data that the cycle does load

`_load_decision_candles` calls `oanda_client.fetch_ohlcv(symbol, "M5", count)` with count from `HYBRID_OHLCV_COUNT` or 200 (`bot_loop.py` 597–632 and 735–736).

`fetch_ohlcv` (`oanda_client.py` 424–453):

- Granularity is M5 on this call.
- Incomplete candles are skipped when `complete` is false.
- If the `complete` field is absent, `dict.get("complete", True)` treats the candle as complete. That is a potential acceptance of a forming bar only when the payload omits the field. OANDA's normal payload includes it. Runtime payloads were not inspected. Evidence: `POTENTIAL_RISK`.
- The decision columns are mid OHLC, not bid or ask (`oanda_client.py` 457–463).
- Duplicate timestamps keep the last row (`oanda_client.py` 410 on the range helper; the latest-count path builds rows in payload order).

When candles load, `_evaluate_impl` reads `close` of the last row as a mid (`bot_loop.py` 755–756) and may persist an M5 shadow market row. That persist is not a trade decision. If a local position exists, management prefers a broker closeout quote for broker-backed rows and the M5 close for paper rows (`bot_loop.py` 802–819).

Candle acquisition failure returns no fabricated bars (`bot_loop.py` 597–612). A missing frame blocks a new entry. An open position is still managed, and the skip reason `MANAGEMENT_CONTINUED_WITHOUT_CANDLES` is logged (`bot_loop.py` 772–776).

## Indicator math, if a caller reached it

`compute_indicators` (`indicators.py` 31–81):

- Rolling means, RSI, ATR as a simple moving average of true range, and Bollinger bands of `2 *` rolling standard deviation.
- Windows look backward, including the current completed bar. That is normal for a closed bar. It is look-ahead only if the current bar is still forming. The fetch path drops `complete == false`.
- Default periods when `lookback` is omitted are MA 5/20, ATR 14, RSI 14.
- A supplied lookback scales those windows with the row count. There is no separate warm-up mask. Early rows are NaN. `volatility_ok` fails closed when the ATR window is short or non-finite (`session_rules.py` 161–197).
- RSI uses a simple rolling mean of gains and losses, not Wilder's smoothing. That is a definition choice, not a sign error.
- No repainting state is stored. A later bar does not rewrite an earlier rolling value inside this function. A restarted process recomputes from the latest fetch.

`SeqModel.predict` (`strategy_meta.py` 35–41) fits a line to the last 50 mids held in RAM and extrapolates one step. It needs 10 points. It is not used on the current production entry path. The series is process-local, so a restart changes it. It is not a trained model.

`compute_nn_pred` (`nn_pred.py` 9–34) is a hint for a voter payload. Unset `NN_PRED_MODE` outside `FOREX_BACKTEST` adds `random.uniform(-0.0005, 0.0005)` to price. It is not a neural network. It is on the unreachable tail only.

## Strategy rules that exist and are not the live voter

`shadow/signals.py` documents that live direction was intended to come from the AI vote plus RL after `select_strategy`, and that shadow uses indicator rules because those live paths have I/O. Rules on the last row:

| Strategy | Rule | Character |
| --- | --- | --- |
| `trend`, `swing_trend` | Buy when fast MA is above slow and close is at or above the fast MA. Sell on the mirror | Trend-following |
| `scalp` | Same comparison with a strict close-versus-fast inequality | Trend-following |
| `mean_reversion`, `swing_mean_reversion` | Sell when close is above the upper band. Buy when close is below the lower band | Deliberate countertrend |
| `swing_breakout` | Buy above the prior high, sell below the prior low, window up to 20 completed bars excluding the current row | Breakout |

A short from `mean_reversion` during a rising market is the written band rule, not an inverted comparison. That rule is not what `run_bot` uses to place an order. `signal_from_arrays` matches `signal_from_indicators`. `build_feature_pack` states that rolling windows use rows at or before `i`.

`select_strategy` (`strategy_meta.py` 159–210):

- If `DECISION_REPAIR_DETERMINISTIC_SELECT` is on, selection is delegated to `decision_repair.selection`. That flag defaults off (`decision_repair/flags.py` 12–13).
- Otherwise, if `HYBRID_<SYMBOL>` is off, selection is a weighted random draw over active strategies (`np.random.choice`).
- If hybrid is on, ATR versus its median chooses the scalp pool or the swing pool, then the same random draw.
- `Strategy.active` is false until assigned the boolean `True` (`strategy_meta.py` 58–64). A fresh process starts every strategy inactive. `live_safety.initialise_fail_closed` applies the durable document and does not treat a stored "allowed" live-order flag as effective permission.

The random draw is not seeded. Two processes, and Windows versus Linux, need not pick the same name. That divergence is latent because this function is not on the current production entry path.

## AI vote and RL

`AIEnsemble.vote` (`ai_ensemble.py` 96–150) aggregates voters. The retired quant stub returns `allow: False` and `direction: None` (`ai_ensemble.py` 40–43). `LocalLLM` and `ExternalLLMAPI` abstain. The default ensemble is built with an empty local list (`ai_ensemble.py` 241–256). External voters are added only when the ensemble mode is `api` or `hybrid` and the corresponding keys are present. This audit did not read those environment variables. With no voters, `vote` returns `no_voters` and `allow` false.

A direction is approved only when one side's confidence weight is strictly greater and the allow score is above 0.5. A tie abstains. `HOLD` abstains. There is no BUY/SELL inversion in `_aggregate_direction`.

`RLAgent.decide` (`rl_agent.py` 28–56) returns `UNAVAILABLE` unless `persisted_ok` is true and the state has one finite unique best action. The constructor leaves `persisted_ok` false. The agent does not sample `epsilon`. On the unreachable tail, `UNAVAILABLE` blocks the entry (`bot_loop.py` 1371–1381). A BUY or SELL from RL must equal the AI side. RL does not override the AI side (`bot_loop.py` 1364–1416).

## Freshness and symbol mapping

`market_provenance.decision_frame_rejection` can return `incomplete_seal`, `stale_bar`, `future_timestamp`, `nonfinite_price`, and `invalid_price` (`market_provenance.py` 354–405). The production shared call reaches that check only after the simulation gate, so the production cycle does not get there. The unreachable broker tail calls it before geometry (`bot_loop.py` 1598–1609).

`symbols.normalize_oanda_symbol` uppercases and maps `-` and `/` to `_`. It does not swap base and quote. The default universe is `EUR_USD`, `GBP_USD`, `USD_JPY`, `AUD_USD`, `USD_CAD`, `USD_CHF` (`symbols.py` 12–18). `FOREX_SYMBOLS` can replace that list. The value in the environment was not read.

## Shorts in a rising market

No active order path implements a short. The mean-reversion shadow rule can propose a sell while price is rising and outside the upper band. That is a deliberate countertrend definition in research/shadow code. It is not evidence that the operational bot is selling into strength. Recent market direction was not measured in this audit.

## Signal findings carried to the register

- Production cycle does not reach feature calculation or a trade candidate (`R66-01`).
- Mid price, not the executable bid/ask, is the candle close used as the decision price (`R66-12`).
- Missing `complete` is treated as complete (`R66-13`, potential).
- Shadow mean reversion is a real countertrend rule and is not the live order path (`R66-14`, informational).
- Unseeded strategy choice and noisy `nn_pred` would diverge across processes if the tail were entered (`R66-15`).
