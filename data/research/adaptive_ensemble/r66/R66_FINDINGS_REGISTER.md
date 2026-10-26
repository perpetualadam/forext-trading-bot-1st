# R.66 Findings register

Severity is about the source as it sits in this working tree. A finding can be source-confirmed and still be off the current `run_bot` entry path. No finding was produced by running the bot. No finding authorises live trading.

Reachability words:

- `ACTIVE_ORDER_PATH` — a scheduled loop can send or locally book a close when its predicate is true.
- `ACTIVE_NON_ORDER_PATH` — the cycle reaches the code and does not submit an order there.
- `UNREACHABLE_IN_CURRENT_GRAPH` — `run_bot` cannot enter it unless the source changes.
- `RESEARCH_ONLY` — not imported by the operational entry graph.

Environment mode, account currency, and broker state were not read. Predicates that depend on them are stated in the consequence. They are not assumed true.

## R66-01

1. ID: `R66-01`
2. Severity: `INFORMATIONAL`
3. Path: `forex_bot/bot_loop.py`
4. Functions: `evaluate_one_instrument_iteration`, `production_adapter_refusal`, `_evaluate_impl`
5. Lines: 1121–1134, 2922–2923, 3321–3328, 4033–4043, 4194–4206
6. Observed: with `simulation=False` the shared decision returns `blocked`. The status `continue_existing_production_broker` is compared once and never assigned. An AST walk found no assignment. `production_adapter_refusal` ends in `production_authority_unavailable` even after the other checks pass. OrderCreate is not called.
7. Expected: a production entry either has an explicit producer seal that authorises one order, or it stays refused. The source matches the refuse side.
8. Evidence: `SOURCE_CONFIRMED`
9. Reachability: `ACTIVE_NON_ORDER_PATH`
10. Consequence: the hybrid, AI, and RL entry described in `strategy_meta.py` does not open trades from `run_bot`. That is a safety property and a documentation mismatch.
11. Correction: none in this stage. A later design would have to add a real producer. Do not flip the status string to wake the legacy tail.
12. Regression: a fixture with `simulation=False` asserts status `blocked`, `broker_requests == 0`, and that `execute_oanda_market_open` is not called. Import must not load `.env` if the test constructs the call without importing `config`.
13. Trading behaviour: a correction that only documents the refusal does not change trading. Enabling the tail would.

## R66-02

1. ID: `R66-02`
2. Severity: `HIGH`
3. Path: `forex_bot/bot_loop.py`
4. Function: `_evaluate_impl` legacy broker tail
5. Lines: 1623–1706
6. Observed: `try_begin_order_submission` runs, then the `try` logs `legacy broker tail is not a dispatch path` and returns. The reservation is not cancelled on that return. The OrderCreate handlers below the return never run. `run_bot` does not enter this tail, because of R66-01.
7. Expected: a reservation that will not be sent is released, and a tail that cannot place an order does not look like the live dispatcher.
8. Evidence: `SOURCE_CONFIRMED`. Runtime entry from `run_bot`: not possible with the current status check.
9. Reachability: `UNREACHABLE_IN_CURRENT_GRAPH`
10. Consequence: none while R66-01 holds. If a later edit returns `continue_existing_production_broker`, the cycle can hold a reservation and still send no order, and the following geometry and fill code stays dead behind the return.
11. Correction: leave it unreachable. A reviewed change would delete or finish the tail in one patch, with the reservation released on every return, and would not enable OrderCreate in the same patch.
12. Regression: call the tail only through a test double of the shared decision that returns the continue status, and assert no OrderCreate and no leftover reservation. Do not point the double at OANDA.
13. Trading behaviour: yes, if someone later connects it. No change is recommended now.

## R66-03

1. ID: `R66-03`
2. Severity: `HIGH`
3. Path: `forex_bot/live_manage.py`
4. Function: `broker_sl_tp_hit`
5. Lines: 76–78, used from `bot_loop.py` 873–880
6. Observed: the function returns false for every position. Broker-backed management never treats the stored stop or target as a reason to close. Paper rows still compare one price with the stored levels.
7. Expected: either a confirmed broker stop remains the hard exit and the local function stays a no-op with that fact recorded per position, or the application enforces a stop when the broker does not have one. A local price field alone does not prove a broker stop.
8. Evidence: `SOURCE_CONFIRMED`
9. Reachability: `ACTIVE_ORDER_PATH` when a broker-backed row is already in RAM. A fresh process has an empty RAM book. Import can create the row (R66-04). The open tail that would create a `live` row is unreachable (R66-01).
10. Consequence: a broker position with no broker stop is not hard-stopped by this function. Weekend flatten and profit protection can still request a close, and for kind `reconcile_import` that close is local only (R66-04).
11. Correction: persist and check `sl_source`. Do not treat `local_fallback` as protected. Do not add a broker amend in this stage.
12. Regression: a broker-backed position with `sl_source=local_fallback` must not be reported as broker-protected. A paper row still hits when the close crosses the stop.
13. Trading behaviour: yes, if management later closes or withholds a close based on the source flag.

## R66-04

1. ID: `R66-04`
2. Severity: `HIGH`
3. Path: `forex_bot/reconciliation.py`, `forex_bot/positions.py`, `forex_bot/trading.py`, `forex_bot/execution.py`
4. Functions: `_apply_position_convergence`, `import_position_from_broker`, `execute_trade`, `close_fill_path`
5. Lines: `reconciliation.py` 530–534 and 638–650; `positions.py` 160–215; `trading.py` 391–398; `execution.py` 225–234; `bot_loop.py` 1058–1084
6. Observed: broker execution mode turns import on even when `RECONCILE_ACTION` is `log_only`. Imported rows use `execution_kind=reconcile_import`. `execute_trade` sends PositionClose only when the kind is `live`. Management still calls `close_position` after a non-live `execute_trade` returns. The reconciliation loop docstring says log-only.
7. Expected: a log-only reconcile does not create a row that management will book as closed. A close of a broker position either sends PositionClose and waits for a full fill, or it leaves both books unchanged.
8. Evidence: `SOURCE_CONFIRMED`. Whether this environment is in broker mode: `NOT_VERIFIED`.
9. Reachability: `ACTIVE_ORDER_PATH` when execution mode is `paper_broker` or `live_broker`, or when `RECONCILE_IMPORT_BROKER_POSITIONS` is set, and a broker position exists. Source default with unset `EXECUTION_MODE` and default `PAPER_TRADING=true` is paper, and import stays off.
10. Consequence: the process can believe it flattened a manual or leftover broker position while OANDA still holds it. The next import can recreate the local row and repeat the local close.
11. Correction: do not import in `log_only`. For any imported row, a protective decision must use the broker close path or must not delete the local row. Separate reviewed change. Not this stage.
12. Regression: synthetic broker snapshot, mode `paper_broker`, action `log_only`, assert no RAM position. A second fixture imports only under an explicit action and asserts a protection decision does not call `close_position` unless a fake PositionClose reports a full fill.
13. Trading behaviour: yes. It changes whether local state and broker state stay aligned. It does not by itself add a strategy.

## R66-05

1. ID: `R66-05`
2. Severity: `HIGH`
3. Path: `forex_bot/reconciliation.py`
4. Function: `_import_broker_truth`
5. Lines: 477–516
6. Observed: if the trade and pending orders do not supply a stop or a target, the import stores a 20-pip fallback and sets `sl_source` or `tp_source` to `local_fallback`. No order is sent.
7. Expected: a missing broker stop stays visible as unprotected. A fallback price is not a protective order.
8. Evidence: `SOURCE_CONFIRMED`
9. Reachability: `ACTIVE_NON_ORDER_PATH` under the same import predicate as R66-04. Combined with R66-03, the fallback does not become a hard close.
10. Consequence: an imported position can sit without a broker stop. This process will not add one on the current graph.
11. Correction: record unprotected explicitly and block any later entry on that symbol until a broker stop is observed. Do not send a new stop order in the audit stage.
12. Regression: trade payload without `stopLoss` yields `sl_source=local_fallback` and a flag `broker_stop_present=false`.
13. Trading behaviour: a later gate that blocks entries would change behaviour only after entries exist. Recording the flag does not.

## R66-06

1. ID: `R66-06`
2. Severity: `MEDIUM`
3. Path: `forex_bot/positions.py`, `forex_bot/profit_protection.py`
4. Functions: `import_position_from_broker`, `seed_position_mfe`
5. Lines: `positions.py` 215; `profit_protection.py` 524–526
6. Observed: import sets `profit_protection_seeded=True`. The next seed returns immediately. MFE starts at 0 and rises only with later management prices.
7. Expected: either seeding is still allowed to reconstruct from post-entry bars, or the position is marked as having an unknown peak so protection does not pretend the peak was observed.
8. Evidence: `SOURCE_CONFIRMED`
9. Reachability: `ACTIVE_NON_ORDER_PATH` after an import. Protection close of a `reconcile_import` row is the local booking in R66-04.
10. Consequence: giveback can arm later than the true peak. It does not arm early from a fabricated peak.
11. Correction: leave `profit_protection_seeded` false until a defined seed runs, or store `mfe_unknown`. Reviewed change.
12. Regression: import then one management price below a historical high in a fixture, assert MFE is not that historical high and the unknown flag is set.
13. Trading behaviour: yes, for when a protection close fires. Not a change to entry signals.

## R66-07

1. ID: `R66-07`
2. Severity: `HIGH`
3. Path: `forex_bot/trading.py`, `forex_bot/portfolio_exposure.py`
4. Functions: `stop_risk_account_ccy`, `quote_pnl_to_account_ccy`, `account_ccy_to_usd`
5. Lines: `trading.py` 148–172; `portfolio_exposure.py` 23–31 and 60–84
6. Observed: stop risk and P&L are computed as a USD approximation. Non-USD quote crosses are returned as if the quote were USD. NAV conversion uses a live mid or a fixed map that includes `GBP: 1.35`. The sizer divides equity by that risk figure and does not take an account currency argument.
7. Expected: risk currency equals the account currency, or the order is refused. A constant such as 1.35 is not a broker GBP rate.
8. Evidence: `SOURCE_CONFIRMED` for the formula. Account currency: `NOT_VERIFIED`.
9. Reachability: `UNREACHABLE_IN_CURRENT_GRAPH` for new sizing. `calculate_pnl` can run when a paper or non-live close computes a local P&L, including a `reconcile_import` close.
10. Consequence: a GBP or other non-USD account would be sized in mixed units if the entry path were enabled. The default six-pair formulas are coherent for a USD account, as the table in the risk audit shows. They are not a spread-bet model.
11. Correction: a later stage should refuse sizing when account currency is missing or not handled, using a synthetic snapshot. Do not read `.env` to discover the currency inside an audit.
12. Regression: the six-pair table, plus EUR_GBP and a GBP account, both of which must fail closed until a conversion exists.
13. Trading behaviour: yes, once sizing is reachable. No change now.

## R66-08

1. ID: `R66-08`
2. Severity: `MEDIUM`
3. Path: `forex_bot/execution_risk.py`, `forex_bot/bot_loop.py`
4. Functions: `_exposure_notional`, shared gross proposal
5. Lines: `execution_risk.py` 192–201; `bot_loop.py` 3861
6. Observed: exposure adds `abs(units) * price` for every symbol. For `USD_JPY`, units are already USD notional, so the product scales with the price.
7. Expected: the same notional helper as `approx_gross_usd_notional_for`, which returns `abs(units)` for `USD_*`.
8. Evidence: `SOURCE_CONFIRMED`
9. Reachability: `UNREACHABLE_IN_CURRENT_GRAPH` (isolated simulation context only)
10. Consequence: a future enabled seam could reject a normal USD_JPY size as over the cap, or compare books that do not match the portfolio helper.
11. Correction: one notional function. Not in this stage, because the seam is closed.
12. Regression: 1000 USD_JPY units at 150 must count as 1000, not 150000, in both helpers.
13. Trading behaviour: only if that seam is later opened.

## R66-09

1. ID: `R66-09`
2. Severity: `MEDIUM`
3. Path: `forex_bot/bot_loop.py`
4. Function: `_evaluate_impl` paper SL/TP test
5. Lines: 876–880
6. Observed: a paper long closes when the management price, the M5 close, is at or below the stop or at or above the target. The bar high and low are not used. A short uses the same single price with the inequalities reversed.
7. Expected: an intra-bar stop test uses the adverse extreme, or the limitation is explicit in the fill model.
8. Evidence: `SOURCE_CONFIRMED`. Sign of the comparison matches the position side.
9. Reachability: `ACTIVE_ORDER_PATH` only for a paper-like row already in RAM. The entry tail that creates those rows does not run. A restarted process has none.
10. Consequence: a paper stop can be missed inside a bar whose close recovers. This does not by itself explain live shorts.
11. Correction: optional later paper-fill model. Do not change it while the entry path is closed unless a paper row can be created another way.
12. Regression: a bar with low through the stop and close back above it must be classified by the chosen rule and asserted, not silently changed.
13. Trading behaviour: yes for paper rows if the rule changes.

## R66-10

1. ID: `R66-10`
2. Severity: `HIGH`
3. Path: `forex_bot/oanda_exec.py`, `forex_bot/bot_loop.py`
4. Functions: `_place_market_order_sync`, `_evaluate_impl` close
5. Lines: `oanda_exec.py` 435–450; `bot_loop.py` 1058–1084
6. Observed: PositionClose returns after parsing a fill price. It does not return the closed unit count. Any non-raising return causes `close_position` of the entire local row.
7. Expected: local size drops only by the units the fill reports. A missing fill keeps the local row and the outcome `ORDER_STATUS_UNKNOWN`.
8. Evidence: `SOURCE_CONFIRMED`. No close was sent.
9. Reachability: `ACTIVE_ORDER_PATH` for a local row whose `execution_kind` is `live`. Creating that kind from the entry tail is unreachable. A row already in RAM from a previous process is not reloaded. So a fresh start has no such row unless some other writer adds one. This audit found no startup loader for positions.
10. Consequence: a partial or empty close body can make the bot believe the position is gone. Import may later recreate it.
11. Correction: require a fill transaction and a unit count before `close_position`. Reviewed change. Not this stage.
12. Regression: a PositionClose body with no fill must leave the RAM row in place. A partial unit count must leave the residual.
13. Trading behaviour: yes, for live closes.

## R66-11

1. ID: `R66-11`
2. Severity: `HIGH`
3. Path: `forex_bot/oanda_exec.py`, `forex_bot/reconciliation.py`
4. Functions: `_place_market_order_sync`, `_may_auto_fix_local`
5. Lines: `oanda_exec.py` 426–433; `bot_loop.py` 686–690 and 1073–1083; `reconciliation.py` 82–84 and 434–446
6. Observed: a timeout becomes `RuntimeError`. The local row stays. The next cycle can send another PositionClose. There is no client id on that request. Default reconcile action `log_only` does not remove a local row just because the broker is flat.
7. Expected: an unknown close is not retried as a new close until a transaction query says the first did not fill. A confirmed flat broker book is then reflected locally once.
8. Evidence: `SOURCE_CONFIRMED`. Timeout behaviour at the broker: `NOT_VERIFIED`.
9. Reachability: `ACTIVE_ORDER_PATH` under the same live-row predicate as R66-10.
10. Consequence: a lost successful close can be followed by another PositionClose against a flat or reduced position. A lost failed close correctly keeps the local row, which is what the code does.
11. Correction: one close attempt identity and a read-only transaction check before a second PositionClose. No network in the unit test.
12. Regression: first response timeout, broker fixture already flat, second cycle must not call PositionClose and must surface `ORDER_STATUS_UNKNOWN` until the fixture supplies a closing transaction.
13. Trading behaviour: yes.

## R66-12

1. ID: `R66-12`
2. Severity: `MEDIUM`
3. Path: `forex_bot/oanda_client.py`, `forex_bot/bot_loop.py`
4. Functions: `fetch_ohlcv`, `_evaluate_impl`
5. Lines: `oanda_client.py` 457–463; `bot_loop.py` 755–756 and 817–819
6. Observed: decision candles use mid OHLC. Paper management uses that mid close. Broker management of an open row uses closeout bid or ask. The unreachable broker entry tail is the place that fetches a fresh bid/ask for a new stop.
7. Expected: a signal and its stop use a stated price side. Mid for a signal and closeout for a flatten can both be valid if the difference is explicit.
8. Evidence: `SOURCE_CONFIRMED`
9. Reachability: candle load is `ACTIVE_NON_ORDER_PATH`. Using the mid as an entry is `UNREACHABLE_IN_CURRENT_GRAPH`.
10. Consequence: no current entry. A later enabled entry that attached stops to mid would place the stop on a price the account cannot execute. The geometry module already exists to avoid that and is not what the cycle runs.
11. Correction: keep mid candles for indicators and require geometry before any future OrderCreate. Do not enable it here.
12. Regression: fixture quote with bid and ask different from mid, assert the stop reference is the executable side for that direction.
13. Trading behaviour: only if entries are enabled.

## R66-13

1. ID: `R66-13`
2. Severity: `LOW`
3. Path: `forex_bot/oanda_client.py`
4. Function: `fetch_ohlcv` and the range candle loop
5. Lines: 382–384 and 450–452
6. Observed: `complete == false` is dropped. A missing `complete` key is treated as true (`dict.get("complete", True)`).
7. Expected: a missing flag is unverified and is dropped, or it is labelled.
8. Evidence: `POTENTIAL_RISK`. Payload shape from a live response was not observed.
9. Reachability: `ACTIVE_NON_ORDER_PATH` for the fetch. The bar is not turned into an order on the current cycle.
10. Consequence: a forming bar could enter the indicator frame if the API omitted the field. That would be a form of look-ahead relative to the bar's close.
11. Correction: treat a missing flag as incomplete.
12. Regression: one candle without the key is excluded.
13. Trading behaviour: no current order impact. A later entry path would change if the last bar disappeared.

## R66-14

1. ID: `R66-14`
2. Severity: `INFORMATIONAL`
3. Path: `forex_bot/shadow/signals.py`, `forex_bot/ai_ensemble.py`, `forex_bot/rl_agent.py`
4. Functions: `signal_from_indicators`, `AIEnsemble.vote`, `RLAgent.decide`
5. Lines: `shadow/signals.py` 54–59; `ai_ensemble.py` 40–43 and 241–256; `rl_agent.py` 28–35
6. Observed: mean reversion sells above the upper band on purpose. That function is not the live voter. The quant stub abstains. The default ensemble has no local voter. RL without `persisted_ok` returns `UNAVAILABLE`.
7. Expected: countertrend rules stay labelled as shadow. An abstaining voter does not open a trade.
8. Evidence: `SOURCE_CONFIRMED`
9. Reachability: shadow rules `RESEARCH_ONLY` relative to OrderCreate. The ensemble object is constructed at import of `bot_loop`, which the process would do if started. The vote function is `UNREACHABLE_IN_CURRENT_GRAPH` from the entry decision.
10. Consequence: a short during a rising market is not produced by the operational order path. Shadow can still describe that signal.
11. Correction: none.
12. Regression: existing direction tests should keep the stub on `allow=false` and `direction=None`.
13. Trading behaviour: no.

## R66-15

1. ID: `R66-15`
2. Severity: `MEDIUM`
3. Path: `forex_bot/strategy_meta.py`, `forex_bot/nn_pred.py`
4. Functions: `_select_from_weights`, `compute_nn_pred`
5. Lines: `strategy_meta.py` 126–136 and 207–210; `nn_pred.py` 29–34
6. Observed: strategy choice uses unseeded NumPy random. The default price hint adds unseeded uniform noise outside backtest mode.
7. Expected: the same inputs produce the same decision on Windows and Linux.
8. Evidence: `SOURCE_CONFIRMED`
9. Reachability: `UNREACHABLE_IN_CURRENT_GRAPH`
10. Consequence: none today. An enabled tail would make strategy identity and the voter payload process-dependent.
11. Correction: do not enable the tail. A later deterministic selector already exists behind `DECISION_REPAIR_DETERMINISTIC_SELECT`, which defaults off.
12. Regression: two calls with a fixed seed, or the deterministic selector, return the same name on both operating systems.
13. Trading behaviour: only if selection is later reached and changed.

## R66-16

1. ID: `R66-16`
2. Severity: `MEDIUM`
3. Path: `forex_bot/app.py`, `forex_bot/bot_loop.py`, `forex_bot/reconciliation.py`
4. Functions: `schedule_trading`, `_evaluate_impl`, `import_position_from_broker`
5. Lines: `app.py` 630–633; `bot_loop.py` 758–789; `reconciliation.py` 638–650
6. Observed: `run_bot` and `reconciliation_loop` are concurrent tasks and both use the RAM position dict. No lock is visible at those two operations. The cycle comment says not to reconcile inside `run_bot`, which avoids a second reconcile call and does not serialise the other task.
7. Expected: import, close, and read of one symbol are ordered.
8. Evidence: `POTENTIAL_RISK`. No interleaving was executed.
9. Reachability: `ACTIVE_NON_ORDER_PATH` as a structure. It becomes an order-path race when R66-04's predicate is true.
10. Consequence: a cycle can manage a row that reconciliation adds or drops mid-loop. The outcome was not observed.
11. Correction: one owner for mutations of `positions`, reviewed with the import fix. Not a new process manager.
12. Regression: a deterministic interleaving in an offline harness that does not open a socket.
13. Trading behaviour: yes, if the lock changes which close happens.

## R66-17

1. ID: `R66-17`
2. Severity: `INFORMATIONAL`
3. Path: `forex_bot/live_safety.py`, `forex_bot/strategy_meta.py`
4. Functions: `initialise_fail_closed`, `Strategy.active`
5. Lines: `live_safety.py` 383–405; `strategy_meta.py` 58–64
6. Observed: effective live-order authorisation is blocked on process start even if the stored document says allowed. Strategies start inactive unless the durable document sets the boolean true. `authorised_for_live` is still not the same as the process live-order flag.
7. Expected: fail closed on start.
8. Evidence: `SOURCE_CONFIRMED`
9. Reachability: `ACTIVE_NON_ORDER_PATH`
10. Consequence: a restart does not silently re-enable new live exposure. Closes of kind `live` are not blocked by this flag.
11. Correction: none.
12. Regression: existing live-safety tests that stay offline.
13. Trading behaviour: no.

## R66-18

1. ID: `R66-18`
2. Severity: `INFORMATIONAL`
3. Path: `data/research/adaptive_ensemble/r62` through `r65`, `forex_bot/research/learning/`
4. Function: none on the operational graph
5. Lines: not applicable
6. Observed: `app.py` and `bot_loop.py` do not import those packages. R.65's boundary still matches this trace.
7. Expected: research containment stays out of the trading cycle.
8. Evidence: `SOURCE_CONFIRMED` for the import headers that were read. Not every research file was read line by line.
9. Reachability: `RESEARCH_ONLY`
10. Consequence: none for orders.
11. Correction: none.
12. Regression: an import scan that fails if `bot_loop.py` imports `r62`, `r63`, `r64`, `r65`, or `ProcessLifecycleManager`.
13. Trading behaviour: no.

## R66-19

1. ID: `R66-19`
2. Severity: `INFORMATIONAL`
3. Path: repository performance artifacts
4. Function: none executed
5. Lines: not applicable
6. Observed: this audit did not run a backtest, query trade storage, or compute return, drawdown, or Sharpe from real trades.
7. Expected: profitability is asserted only from a reviewed sample.
8. Evidence: `NOT_VERIFIED`
9. Reachability: not an order defect
10. Consequence: no performance claim is available.
11. Correction: none until a separate offline evidence review is scoped. It must not use live credentials.
12. Regression: not a trading regression.
13. Trading behaviour: no.

## Counts

| Severity | IDs |
| --- | --- |
| CRITICAL | none |
| HIGH | R66-02, R66-03, R66-04, R66-05, R66-07, R66-10, R66-11 |
| MEDIUM | R66-06, R66-08, R66-09, R66-12, R66-15, R66-16 |
| LOW | R66-13 |
| INFORMATIONAL | R66-01, R66-14, R66-17, R66-18, R66-19 |

R66-02, R66-07, R66-08, and R66-15 are high or medium in the source and unreachable from today's `run_bot` entry path. The high findings that sit on a scheduled loop are R66-03, R66-04, R66-05, R66-10, and R66-11, each with the predicate in the entry above. None of them was observed against a live account.
