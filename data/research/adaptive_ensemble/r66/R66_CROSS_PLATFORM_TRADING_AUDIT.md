# R.66 Cross-platform trading audit

The order, sizing, stop, and signal modules that this audit traced do not branch on `os.name` or `sys.platform`. The Windows-only reparse check in `forex_bot/research/adaptive_ensemble/g10_audit.py` is not imported by `app.py` or `bot_loop.py`. Windows and Linux are intended to share the trading code. This audit did not execute that code on either system. Behavioural equivalence is `NOT_VERIFIED` by a run. The differences below are source-visible.

## Where identical inputs can still diverge

| Topic | Source | Effect if that code runs | On the current `run_bot` entry path |
| --- | --- | --- | --- |
| Unseeded `np.random.choice` in `select_strategy` | `strategy_meta.py` 126–136 | Different strategy name across processes and operating systems | No |
| `random.uniform` in `compute_nn_pred` when mode is noise or unset outside backtest | `nn_pred.py` 29–34 | Different voter payload | No |
| `random.choice` fallback when hybrid weights are empty | `strategy_meta.py` 209 | Different strategy name | No |
| Binary float sizing and P&L | `trading.py` `position_sizing`, `pnl_account_ccy` | Usually identical for the same IEEE operations. Not a decimal contract. Summation order of a portfolio could differ if dict order differed. CPython 3.7+ dicts preserve insertion order on both Windows and Linux | Sizing no. A live close uses broker P&L when present |
| `datetime.utcnow` for a new position timestamp | `bot_loop.py` 1865 | Naive UTC. Comparable if both sides treat it as UTC. Easy to mix with aware timestamps | No, unreachable tail |
| Session clocks | `session_rules.py` uses UTC helpers for the injected path (`flatten_for_weekend_at`, `in_active_session_at`) | The shared function requires an injected `now`. The production cycle passes `datetime.now(timezone.utc)` (`bot_loop.py` 4382). Weekend and session on the early `_evaluate_impl` check call the non-injected helpers | Yes for the early block. A timezone-naive local clock is not what the shared function uses |
| Paths | `live_safety.state_path` and database configuration use `pathlib` and host strings | Case-sensitive filesystems can miss a state file that Windows would open. That changes fail-closed safety state, not an indicator value | Yes if the process starts. Not compared across hosts here |
| PostgreSQL | `database.py` | Lock and isolation behaviour was not reviewed statement by statement | `NOT_VERIFIED` |
| Locale | Floats are parsed with `float()`, which accepts a dot and does not use the locale | Low risk for prices | Not executed |
| Random seed | No trading seed is set in the traced modules | Any `random` or `numpy` call diverges | Those calls are off the entry path |
| Model files | No model load on the traced entry path. RL starts with `persisted_ok` false | A future persisted table would need identical bytes and an explicit load | Not active |
| Threads | Reconciliation and `run_bot` are separate asyncio tasks | Scheduling can change which task touches `positions` first. That is concurrency, not an indicator formula | Yes as a source structure. Not timed |
| Multiprocessing | Not used on the traced trading path | None | No |
| Environment defaults | Same code, different environment files | Different symbols, risk fractions, and execution mode. That is configuration, not an OS formula | `NOT_VERIFIED` because `.env` was not read |

Indicator formulas (`rolling`, `ewm`, `percentile`) are NumPy and pandas operations. Given the same versions and the same candle rows, they are expected to match. Version parity was not checked on a Linux host in this stage. WSL was not used. Linux result: `NOT_VERIFIED`.

`execution_risk` file replacement uses a path from configuration (`execution_risk.py` `_save`). Whether that replace is atomic on both operating systems was not tested. The function is not on the production entry path.

## What must stay equivalent

If a later stage enables entries, the same candle rows, the same quote, the same account snapshot, and the same configuration should produce the same direction, the same unit count, the same stop and target, and the same order payload on Windows and Linux. The current unseeded draws and the noise hint would violate that. They should not be part of an enabled path.

The active management comparison for paper stops uses a single price. That comparison itself is deterministic. The broker closeout path is deterministic given the same quote.

## Fixtures worth adding later

Do not add them in this stage. A later offline test can feed plain numbers into copies of the pure formulas, or into functions imported only after a test harness that does not call `load_dotenv`. Suggested cases, all synthetic:

1. EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF: 20-pip stop, equity 10_000, risk 1%, assert the unit counts in the risk audit table within a stated tolerance.
2. BUY and SELL stop orientation around a reference, including a JPY pip of 0.01.
3. Profit-protection ratchet: a second, lower MFE must not reduce `profit_protection_exit_pips`.
4. A completed M5 frame versus a frame whose last bar is incomplete, asserting the incomplete bar is absent when `complete` is false, and recording the missing-key behaviour explicitly.
5. The same fixture run on Windows and on Linux with pinned dependency versions, comparing direction, units, stops, and the OrderCreate body dict with `production_authorised` left false and no network.

No new process manager and no merge of R.62–R.65 belong in that test.
