# R.66 Trade-decision audit

Source review only. No order path was executed.

## Production cycle, no local position

Function chain, not executed:

1. `app.schedule_trading` creates the `run_bot` task (`app.py` 618–633).
2. `run_bot` calls `_cycle_symbols` then `evaluate(symbol)` with no dependency object (`bot_loop.py` 4402–4410, 693–710).
3. `evaluate` calls `_evaluate_impl` (`bot_loop.py` 713–725).
4. `_load_decision_candles` loads M5 bars or returns none (`bot_loop.py` 597–632).
5. `get_position`. On failure the symbol is skipped and new exposure is not opened (`bot_loop.py` 758–771).
6. If there is no position and the session is closed or weekend flatten is set, the function returns. Those gates block new entries only (`bot_loop.py` 777–786).
7. `dispatch_production_iteration` → `evaluate_one_instrument_iteration` with `simulation=False`, `invoke_selector/vote/rl=True`, and `broker=None` (`bot_loop.py` 4370–4398).
8. The shared function checks candles, an injected clock, weekend, session, an existing position, exposure hold, and a pending broker exit (`bot_loop.py` 3256–3319).
9. At the permission phase, `simulation` is false, so it returns `status=blocked` with `blocked_by` equal to `pre_trade_entry_blocked_reason()` or `production_path_has_no_simulation_context` (`bot_loop.py` 3321–3328).
10. `_evaluate_impl` logs `shared_entry_blocked` and returns (`bot_loop.py` 1121–1134).

Nothing after line 1134 runs on this path. That includes the second exposure check, the strategy gate, volatility, the AI vote, RL, sizing, notional and portfolio caps, the USD-direction guard, entry geometry, reservation, and `open_position`.

`production_execution_adapter` (`bot_loop.py` 3103–3163) is the only production call site of `execute_oanda_market_open`. Its docstring states that no current producer can seal `production_eligible` true. `production_adapter_refusal` returns a refusal reason on every branch, and the last successful-looking branch still returns `production_authority_unavailable` (`bot_loop.py` 2922–2923). The OrderCreate call below that return is not reached for any dictionary this producer builds. The shared function also returns `production_entry_ineligible` unless `simulation` and an isolated-test account context are both set (`bot_loop.py` 4033–4043), and it withholds the adapter when `simulation` is false (`bot_loop.py` 4194–4206). A simulation dispatch records a fake broker. It does not call OANDA.

## Production cycle, local position already open

This chain is on the scheduled loop. It runs only when `positions` already contains the symbol.

1. Session and weekend do not skip management (`bot_loop.py` 778).
2. New entries are skipped with `POSITION_ALREADY_OPEN` (`bot_loop.py` 788–789).
3. Broker-backed rows (`execution_kind` `live` or `reconcile_import`, or `broker_order` true) take a pricing snapshot and `resolve_broker_manage_price`. BUY uses closeout bid. SELL uses closeout ask (`live_manage.py` 33–73). There is no fallback to the M5 close. A stale or missing quote yields no management price.
4. Paper-like rows use the M5 close (`bot_loop.py` 817–819).
5. `apply_profit_protection` may request a close. If the management price is missing, a broker-backed row forces `protect_hit` false (`bot_loop.py` 882–883).
6. `broker_sl_tp_hit` is false for every broker-backed row (`live_manage.py` 76–78). Paper rows compare the management price with the stored stop and target (`bot_loop.py` 876–880). A long hits when price is at or below the stop or at or above the target. A short hits on the mirror. The comparison uses one price, not the bar high and low.
7. Weekend flatten can close even when stop, target, and protection did not hit (`bot_loop.py` 894–897).
8. Uncertain side or non-positive size withholds the close (`bot_loop.py` 898–909).
9. A minimum hold defers a pure SL/TP touch. It does not defer weekend flatten or profit protection (`bot_loop.py` 910–925).
10. `close_fill_path`: kind `live` requires a broker close or aborts (`execution.py` 225–234). Abort does not drop the local position.
11. `execute_trade` then `close_position` (`bot_loop.py` 1058–1084). The local row is removed only after `execute_trade` returns. An exception keeps the local row.

## Gates that exist and where they sit

| Control | Where it is enforced on the current cycle |
| --- | --- |
| Live-order auth blocked at process start | `live_safety.initialise_fail_closed`. Also inside `pre_trade_entry_blocked_reason`, which the shared function may use as the block reason before it returns |
| Strategy inactive / not authorised | Unreachable tail and the shared function after the simulation return |
| Session and weekend for new risk | `_evaluate_impl` before the shared call, and again inside the shared function |
| One local position per symbol | `get_position` returns into the management branch |
| Exposure, pending exit, reconcile staleness | Shared function before the simulation return, so they can be the `blocked_by` string. They are not a second independent order path |
| AI allow and direction | Unreachable from `run_bot` |
| RL agreement | Unreachable from `run_bot` |
| Volatility filter | Unreachable from `run_bot` for entries. Paper close still computes ATR when simulating a fill |
| Sizing, notional, portfolio stop-risk, USD-direction | Unreachable tail, and the shared function only after simulation is true |
| `execution_risk.entry_risk_block` | Shared function only in an isolated simulation context |
| Client-order reservation | Unreachable legacy tail and the simulation reservation inside the shared function |
| Fresh bid/ask geometry | Unreachable legacy tail |

`pre_trade_entry_blocked_reason` (`execution.py` 143–195) combines halt, kill switch, live-order auth, optional account-risk and exposure flags (default off), and reconcile freshness. The production shared call does not treat a passing permission as permission to trade. A `None` permission becomes `production_path_has_no_simulation_context`.

## Paths that do not open a new broker order

- HTTP `/set_mode` updates `Config.TRADING_MODE` (`app.py` 836–872). It does not call OrderCreate.
- `evolve` can disable a strategy. With the health flag off it does not activate one (`bot_loop.py` 1926 onward; `live_safety.persist_evolve_disable`).
- `v2_shadow` market persist writes an observation. It does not submit an order.
- Research learners under `forex_bot/research/learning/` are not imported by `app.py` or `bot_loop.py`.
- R.62–R.65 process managers are not imported by the operational package.

There is one OrderCreate function, `_place_market_order_open_sync`, and one production caller, `production_execution_adapter`. The current producer does not reach that caller. There is not a second live entry engine that bypasses these gates.

## Fail-closed behaviour that is present

- No candles: no new entry.
- Position state exception: no new entry.
- Shared decision any status other than the never-produced continue status: no new entry.
- Live close while broker orders are disabled: local position kept, close aborted.
- Close exception: local position kept.
- `production_adapter_refusal` refuses before OrderCreate, including a fully checked dictionary, with `production_authority_unavailable`.

## Fail-closed gap on a path that is not currently entered

The legacy tail in `_evaluate_impl` calls `try_begin_order_submission` (`bot_loop.py` 1623–1634) and later hits `logger.error("%s: legacy broker tail is not a dispatch path")` and `return` (`bot_loop.py` 1705–1706). The `return` is inside `try`, before OrderCreate. The reservation is not cancelled on that line. The except handlers below it are unreachable because the `try` body returns first. This matters only if a future edit makes `evaluate_one_instrument_iteration` return `continue_existing_production_broker`. Today `run_bot` cannot enter it. See `R66-02`.

## Race and retry notes

Symbols are handled one at a time in a single `run_bot` task. Reconciliation runs in another task (`app.py` 630 and 158–170). Both can touch `positions`. The cycle comment says reconciliation is the only mutator of broker comparison and that the cycle should not reconcile concurrently (`bot_loop.py` 4407). The two tasks still share the in-memory book without a lock visible at the `get_position` / `import_position_from_broker` boundary. A cycle can manage a row that reconciliation imports or removes between symbols. Evidence is the two call sites, not a reproduced interleaving. See `R66-16`.

Duplicate new orders are not produced by the current cycle because the cycle does not submit new orders. Close retries are covered in the execution audit.
