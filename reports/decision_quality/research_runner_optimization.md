# Research runner optimization

Research-only. Production trading was not changed. Historical CSVs were not modified.

Started: 2026-09-18T09:35:26Z

---

## Stage 1 — Static performance inspection

**Status:** COMPLETED  
**Started:** 2026-09-18T09:35:26Z  
**Finished:** 2026-09-18T09:36:19Z  
**Elapsed:** 53s (00m 53s)

### Call chain (VERIFIED)

```
__main__.main
  inventory_local_ohlcv  → load every CSV once
  for each series with bars > warmup:
    load_symbol_frame
    run_symbol_backtest(... baseline ...)
    for mult in (1.0, 1.25, 1.5, 2.0):
      run_symbol_backtest(... sl_atr_mult=mult ...)   # FULL replay
  write_reports  # only after ALL runs
```

`run_symbol_backtest` walks `i in range(warmup, len(df))`.

### Work INSIDE the per-bar loop (every bar)

| Operation | File | Notes |
|---|---|---|
| `parse_bar_time` | `execution_sim` | cheap |
| `history_at(df, i)` | `data.py` | **`df.iloc[:i+1].copy().reset_index`** — full prefix copy every bar |
| If position open | `engine` | high/low SL/TP + `continue` — **skips signal** |
| Else `evaluate_signal(window, ...)` | `signal.py` | see below |
| Append `DecisionSnapshot` | `engine` | one large object per evaluated bar |

### Work inside `evaluate_signal` (bars with no open position)

1. `fx_market_open_at(now)` (session hours off in default runner)
2. **`compute_indicators(raw, route_lookback)`** — copy + rolling/ewm on **entire prefix**
3. `seeded_select_strategy` — save/restore global RNGs + `select_strategy`
4. **`production_quant_decision` → `compute_indicators(raw, lookback)` again**
5. `volatility_ok`, `_quant_stub_vote`, SL/TP distances
6. **`_snapshot` always** (signal or no-signal):
   - **`indicator_research_fields` → `compute_indicators` a third time** + `wilder_adx` (prefix ewm) + `atr_percentile`
   - **`htf_trend_labels` → `resample_closed_ohlc` for M15, H1, H4** each does `_asof_mask` copy + `resample` of the growing prefix
   - `simulated_half_spread`, `pip_size`, `DecisionSnapshot(...)`

`compute_indicators` itself starts with `out = df.copy()`.

### Static bottleneck hypothesis (not yet profiled)

1. **Dominant:** repeated full-prefix `compute_indicators` (2–3× per empty bar) + **HTF resample of the growing prefix** (3 rules × every empty bar) + **`history_at` copy**.
2. Complexity if each empty-bar call is Θ(i): **Θ(N²)** in bars for one `run_symbol_backtest`.
3. **ATR 1.00/1.25/1.50/2.00 repeat the entire signal path.** Invariant across those runs: indicators, routing, quant side, HTF, research fields, session. Only SL/TP distances and simulated outcomes change.
4. **No incremental I/O:** reports written only after 30 sequential runs.
5. Snapshots retained for every evaluated bar (memory; secondary to CPU).
6. `finalize_trade` / forward returns run **per trade**, not per bar — unlikely the 35-hour driver.

`compute_indicators` period lengths stabilize after warmup for lookbacks 50/100 (`ma_slow` ≤ 50 < warmup 80). Prefix-at-i last row should match full-history `iloc[i]` **for those lookbacks** — relevant to later optimization, not implemented here.

No optimization in this stage.

---

## Stage 2 — Profile a representative small workload

**Status:** COMPLETED  
**Started:** 2026-09-18T09:36:47Z  
**Finished:** 2026-09-18T09:37:47Z  
**Elapsed:** 60s (01m 00s)

Existing implementation only. No code changes to the backtester.

### Workload

- Symbol: EUR_USD
- File: `data/historical/EUR_USD_M5.csv` (read-only; first **800** rows)
- `run_symbol_backtest` once, warmup=80, seed=42, fx_week on, session hours off
- Command: `PYTHONPATH=. python reports/decision_quality/_profile_small_backtest.py`
- Artifact: `reports/decision_quality/profile_small_eurusd_800.txt`

### Results

| Metric | Value |
|---|---|
| Wall time | **4.8485 s** |
| cProfile total | 4.842 s |
| Function calls | 6,550,581 |
| Signals / trades | 35 / 35 |
| Snapshots (`evaluate_signal` calls) | **70** (not 720: open positions skip signal) |

### Top cumulative

| Function | ncalls | cumtime (s) | share of 4.84s |
|---|---|---|---|
| `run_symbol_backtest` | 1 | 4.844 | 100% |
| `evaluate_signal` | 70 | 3.661 | 76% |
| `signal._snapshot` | 70 | 2.377 | 49% |
| `compute_indicators` | 210 (3× per eval) | 1.674 | 35% |
| `htf_trend_labels` | 70 | 1.410 | 29% |
| `resample_closed_ohlc` | 210 | 1.257 | 26% |
| `finalize_trade` / `observe_after_stop` | 35 / 25 | 0.976 / 0.969 | 20% |
| `indicator_research_fields` | 70 | 0.942 | 19% |
| `production_quant_decision` | 70 | 0.612 | 13% |
| `wilder_adx` | 70 | 0.327 | 7% |

### Top self time

Pandas/object overhead: `isinstance`, `Series.__init__`, `sanitize_array`, datetime inference. `observe_after_stop` is the hottest **project** self-time (0.041s × 25, cum 0.969s) via `iterrows`.

Empirical: on this 800-bar slice, **signal + research snapshot + HTF resample + triple indicator compute** dominate. Trade-exit observation is material per trade but not the per-bar prefix copy itself (positions skip `evaluate_signal`).

---

## Stage 3 — Explain the 35-hour failure mode

**Status:** COMPLETED  
**Started:** 2026-09-18T09:38:10Z  
**Finished:** 2026-09-18T09:38:54Z  
**Elapsed:** 44s (00m 44s)

### Scaling evidence (same existing `run_symbol_backtest`, EUR_USD prefix)

| bars | wall_s | evals | trades | s/eval |
|---|---|---|---|---|
| 400 | 1.435 | 47 | 19 | 0.0305 |
| 800 | 2.539 | 70 | 35 | 0.0363 |
| 1600 | 5.404 | 117 | 61 | 0.0462 |
| 2400 | 10.998 | 200 | 101 | 0.0550 |

Bars ×3 (800→2400) ⇒ time ×4.33; evals ×2.86; **cost per eval rose 1.51×** as prefixes grew. That is **superlinear**, consistent with each `evaluate_signal` costing **Θ(prefix length)** (indicators + 3× resample + ADX).

Eval count is **not** N: open positions skip `evaluate_signal`. Cost is **Θ(Σ prefix_len over empty bars)**.

- If almost every bar is empty (few/no trades): **Θ(N²)**.
- If positions occupy most bars: closer to **Θ(N × trades × avg_prefix)** still growing with N.

### Why ~450 bars was fine and ~75,000 × 30 was not

450-bar sample: handful of evals, small prefixes, seconds.

~74,500 M5 bars: later evals run `compute_indicators` + HTF `resample` on **tens of thousands of rows**, three indicator passes, three timeframes. Profile: 70 evals @ ~800-bar prefixes already **3.66s** in `evaluate_signal`.

Rough bound from measured 55 ms/eval at ~2.4k bars, if cost ∝ prefix and mean prefix ≈ N/2 ≈ 37k (~15× 2.4k): **~0.8 s/eval**.  
Worst case ~74k evals ⇒ **on the order of 16 hours per `run_symbol_backtest`**.  
30 sequential runs ⇒ **many tens of hours**, matching a ~35-hour kill with **no report** (writes only at the end).

This is an order-of-magnitude estimate from measured s/eval growth, not a remaining-time prediction for a live job.

### Smallest bottleneck set

1. **Per-eval full-prefix `compute_indicators` × 3** (route, quant, research).
2. **Per-eval HTF resample M15/H1/H4** of the growing prefix.
3. **30× sequential full replays** (6 symbols × baseline+4 ATR) repeating identical signal work.
4. **No checkpoint / no incremental report.**

Secondary: `observe_after_stop` `iterrows` (~20% on the 800-bar profile) scales with **trades**, not N².

Complexity claim: **dominated by repeated Θ(prefix) dataframe work; worst-case Θ(N²) when most bars evaluate.** Evidence: profile ncalls + rising s/eval with N.

---

## Stage 4 — Optimization design (written before implementation)

**Status:** COMPLETED  
**Started:** 2026-09-18T09:39:25Z  
**Finished:** 2026-09-18T09:39:45Z  
**Elapsed:** 20s (00m 20s)

### Constraint

Trading semantics of the **current** offline engine must not change. No production files. No RL. No ATR-width preference.

### Keep a reference path

Leave today’s `evaluate_signal` + `history_at` + per-bar `compute_indicators` callable as `run_symbol_backtest_reference` (or `impl="reference"`). Default research runner will switch to `impl="optimized"` only after equivalence tests pass on fixtures.

### Proposed changes (research package only)

1. **Precompute production indicators once per lookback** used by routing/quant (`HYBRID_ROUTE_LOOKBACK`, `SCALP_LOOKBACK`, `SWING_LOOKBACK`, `DEFAULT_INDICATOR_LOOKBACK`) on the full chronological frame. After warmup (80), period lengths for these lookbacks are already at their uncapped values, so `iloc[i]` of the full-series compute matches last-row of a prefix compute (causal rolling/ewm).  
   If a lookback appears that was not cached, compute that series once and cache it.

2. **Do not copy `df.iloc[:i+1]` on every bar.** Pass the full frame plus index `i`. Signal functions may only read `iloc[:i+1]` / `iloc[i]`.

3. **Precompute closed HTF OHLC once** (M15/H1/H4) with the same `resample(..., label="left", closed="left")` and drop-incomplete rule as `resample_closed_ohlc`. At bar time T, use only HTF rows whose **period end ≤ T**. Do not expose the in-progress candle. M5 trend label uses only closes at or before T.

4. **Precompute research fields (ADX, ATR percentile inputs)** from the cached indicator frame; at bar i use values at i only (ADX ewm is causal).

5. **Call `compute_indicators` O(lookbacks) per symbol, not O(evals).** Quant vote still uses `_quant_stub_vote` on the cached last-row features at i.

6. **Separate signal generation from outcome simulation.**  
   - Pass 1: emit per-bar decisions (side / no-signal, strategy, horizon, mid, ATR, research snapshot fields).  
   - Pass 2: walk opens/exits with a given SL/TP rule (production distances or `sl_atr_mult`).  
   Baseline and ATR experiments then share pass 1. This task will **not** run ATR experiments; the split is for future work units.

7. **Do not change** `_quant_stub_vote`, `select_strategy` algorithm, `volatility_ok`, `fx_market_open_at`, `sl_tp_from_production_distances`, `bar_touches` ambiguity policy, or spread half-spread function. Seeded routing stays `seed + i * 10007 + hash(symbol)%100000`.

### Lookahead protections

- Cached series at index i may only depend on bars `0..i`.
- HTF lookup uses closed bars only (`index + offset <= asof`), same as today.
- Warmup: still skip `i < warmup`.
- NaNs: same `compute_indicators` implementation; do not fill.
- Equivalence tests (Stage 5) must fail on shifted signals / changed SL/TP / changed exits.

### Explicitly rejected here

- Changing indicator formulas or lookback env defaults.
- Approximate / incremental pandas that would change EMA/ADX warmup vs a prefix recompute.
- Adding RL to the engine.
- Parallelizing 30 ATR runs as the first step (signals must be shared first).

### Expected effect

Per symbol: O(N) indicator + HTF precompute, then O(N) bar walk with O(1) feature reads. ATR variants become O(N) outcome walks on stored signals, not 5× signal recompute.

---

## Stage 5 — Equivalence tests (before optimization)

**Status:** COMPLETED  
**Started:** 2026-09-18T09:40:09Z  
**Finished:** 2026-09-18T09:41:42Z  
**Elapsed:** 93s (01m 33s)

Added `tests/test_decision_quality_equivalence.py` against the **current** `run_symbol_backtest` (250-bar EUR_USD historical prefix, read-only).

Locks: snapshot decision sequence (7 BUY/SELL among 29 evals), trade count 7, sides, exit reasons (`sl/sl/tp/sl/sl/sl/eod`), SL/TP side geometry, MFE/MAE present, prefix-only `evaluate_signal`, in-process determinism.

`test_optimized_impl_matches_reference_when_present` skips until `impl="optimized"` is wired (Stage 6).

Command: `python -m pytest tests/test_decision_quality_equivalence.py -q --tb=short`  
Result: **4 passed, 1 skipped** in 6.19s.

---

## Stage 6 — Implement performance optimization

**Status:** COMPLETED  
**Started:** 2026-09-18T09:42:48Z  
**Finished:** 2026-09-18T09:47:31Z  
**Elapsed:** 283s

Wired `impl="reference"` (unchanged default) and `impl="optimized"` in `run_symbol_backtest`.

Optimized path (`fast_cache.py`):
- `SignalCache` precomputes `compute_indicators` once per lookback and closed M15/H1/H4 OHLC once.
- Per-bar `evaluate_signal_cached` reads prefix-correct indicator rows. If `_period_tuple(lookback, i+1)` differs from the full-frame periods (short prefixes), it recomputes the prefix so MA/ATR lengths match the reference.
- HTF labels use only bars with period end <= asof (same closed-candle rule as `resample_closed_ohlc`).
- VOLATILITY_FILTER / FX_WEEK / SESSION / NO_STRATEGY match `_blank`: lookback field 0, empty vote, research fields at lookback 50.
- Trade simulation, SL/TP, spread, and `bar_touches` are unchanged and shared.

First equivalence compare failed only on snapshot `lookback` (reference `_blank` uses 0 on VOLATILITY_FILTER; optimized had passed the strategy lookback). Decision/side/SL/TP/exits already matched. After matching `_blank`, equivalence passed.

Command: `python -m pytest tests/test_decision_quality_equivalence.py -q --tb=short`  
Result: **5 passed** in 6.30s.

No production trading files changed. Historical CSVs not modified. Default engine `impl` remains `reference` so existing tests stay on the original path.

---

## Stage 7 — Baseline progress / checkpoint / resume

**Status:** COMPLETED  
**Started:** 2026-09-18T09:47:42Z  
**Finished:** 2026-09-18T09:49:21Z  
**Elapsed:** 99s (01m 39s)

Six baseline work units follow canonical `DEFAULT_FOREX_SYMBOLS` order:

1. EUR_USD baseline  
2. GBP_USD baseline  
3. USD_JPY baseline  
4. AUD_USD baseline  
5. USD_CAD baseline  
6. USD_CHF baseline  

The CLI default is now `--mode baseline` (no automatic ATR widths). Each unit prints START, writes `checkpoints/baseline/{symbol}__baseline.json` immediately, updates `baseline_checkpoint.json` atomically, prints FINISH + elapsed + trade count.

Resume skips `status=completed` units. A unit left `running` is redone. Incompatible identity (warmup/seed/impl/session flags/env/code hash/unit set) raises `CheckpointIncompatibleError` / exit 2. `--force-rerun` rebuilds the checkpoint.

Identity stored per run: warmup, seed, impl, session flags, research env (`HYBRID_ROUTE_LOOKBACK`, lookbacks, SL/TP env, FX week env), sha256 of research+indicator/SL/TP source files, and per-symbol CSV path/sha256/size/mtime.

CLI default `--impl optimized`. Engine API default remains `reference`.

Command: `python -m pytest tests/test_decision_quality_checkpoint.py tests/test_decision_quality_equivalence.py tests/test_decision_quality_engine.py::test_package_cannot_reach_broker_writes -q --tb=short`  
Result: **12 passed** in 10.13s.

The six-symbol 12-month baseline was **not** launched.

---

## Stage 8 — Separate baseline from experiments

**Status:** COMPLETED  
**Started:** 2026-09-18T09:49:53Z  
**Finished:** 2026-09-18T09:50:53Z  
**Elapsed:** 60s (01m 00s)

Baseline is the default CLI (`--mode baseline`). It schedules exactly six `{symbol}|baseline` units and never launches ATR widths.

Stop-width capability is kept as an **explicit** `--mode stop_width` runner with the same checkpoint/resume system. Planned future work units (not executed on the 12-month dataset):

- `{symbol} ATR 1.00` / `1.25` / `1.50` / `2.00` for each of the six pairs (24 units)
- Separate file: `stop_width_checkpoint.json`
- Unit IDs such as `AUD_USD|atr_1.00`

No preferred ATR width was selected. The 24-run historical experiment was not started. A one-symbol / one-width synthetic plumbing test confirmed the work-unit API only.

Command: `python -m pytest tests/test_decision_quality_checkpoint.py -q --tb=short`  
Result: **10 passed** in 6.24s.

---

## Stage 9 — Fix stale historical inventory test

**Status:** COMPLETED  
**Started:** 2026-09-18T09:51:26Z  
**Finished:** 2026-09-18T09:51:52Z  
**Elapsed:** 26s (00m 26s)

`test_inventory_reports_missing_pairs` expected five symbols to have 0 bars. That premise is obsolete after the approved six-pair download.

Updated `tests/test_decision_quality_data.py`:
- `test_inventory_reports_required_six_pairs_present` asserts EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF each have a real M5 CSV, bars>0, path on disk, earliest/latest set.
- `test_inventory_reports_missing_pairs` now uses an isolated temp dir with only EUR_USD so it still fails closed if a required pair is genuinely absent (`bars==0`, `path is None`, missing_reason contains `no local CSV`).

Test was not deleted and not weakened into a tautology.

Command: `python -m pytest tests/test_decision_quality_data.py -q --tb=short`  
Result: **5 passed** in 2.19s.

Historical CSV contents were not modified.

---

## Stage 10 — Validate performance without the full baseline

**Status:** COMPLETED  
**Started:** 2026-09-18T09:52:54Z  
**Finished:** 2026-09-18T09:55:00Z  
**Elapsed:** 126s (02m 06s)

Same bounded EUR_USD prefix as Stage 2 (first 800 historical M5 bars), plus scale windows. Script: `reports/decision_quality/_bench_optimized.py`. Outputs: `bench_optimized_vs_reference.txt` / `.json`.

| bars | REFERENCE | OPTIMIZED | speedup | equivalent trades |
| ---: | ---: | ---: | ---: | ---: |
| 400 | 1.3924s | 0.3678s | 3.79x | yes |
| 800 | 2.3692s | 0.8160s | 2.90x | yes (full snapshot compare) |
| 1600 | 5.2637s | 2.2505s | 2.34x | yes |
| 2400 | 10.5882s | 5.0216s | 2.11x | yes |
| 5000 | — | 21.1379s | — | n/a |
| 8000 | — | 46.8241s | — | n/a |

Headline 800-bar outputs are equivalent (decisions, lookbacks, trade tuples).

Linear projection from 8000-bar optimized (46.8241s) at 74555 bars: **~436s per symbol**, **~2618s (~44 min) for six sequential symbols**.

Optimized runtime still grows faster than linear (8000/2400 = 3.33× bars, 46.8/5.02 = 9.3× time). Remaining cost is likely `finalize_trade` / `observe_after_stop` (`iterrows` over the suffix) plus per-eval `select_strategy` / snapshot construction. A pessimistic quadratic-ish extrapolation is a few hours for six symbols, not tens of hours.

**Six-symbol 12-month baseline was not launched.**

Readiness: YES for a checkpointed next operation (measured minutes-to-hours, resume-safe), with remaining superlinear trade-sim cost documented.

---

## Final regression

**Command:** `python -m pytest -q --tb=line`  
**Started:** 2026-09-18T09:55:33Z  
**Result:** **316 passed, 0 failed, 0 skipped** in **27.09s**

The previously stale `test_inventory_reports_missing_pairs` now validates the current six-pair inventory and still detects a genuinely missing required CSV in an isolated directory.

No 12-month baseline, ATR experiments, RL historical experiments, downloader, real external APIs, or broker writes were launched.

---

## Final report (required answers)

1. **Root cause of the 35-hour runtime.** Each empty bar copied the growing prefix and ran `compute_indicators` 2–3 times plus three HTF resamples of that prefix. That is Θ(prefix) work per eval → worst-case **Θ(N²)** per `run_symbol_backtest`. The CLI then repeated the full signal path 5 times per symbol (baseline + 4 ATR widths) = 30 sequential runs, and wrote reports only after all 30 finished. ~75k bars × 30 silent in-memory runs is the 35-hour failure mode.

2. **Profiling evidence.** Stage 2 cProfile on 800 EUR_USD bars: 4.85s, 70 evals (open positions skip), 76% in `evaluate_signal`, 210 `compute_indicators` calls. Stage 3 scale: 400/800/1600/2400 = 1.44/2.54/5.40/11.00s (s/eval rising). Artifacts: `profile_small_eurusd_800.txt`, `bench_optimized_vs_reference.json`.

3. **Major bottlenecks.** Prefix `history_at` copy; repeated `compute_indicators`; per-bar M15/H1/H4 resample; `_snapshot` research/ADX; 5× full replay for ATR; no checkpoint.

4. **Complexity/scaling.** Empirically superlinear: per-eval cost grew with prefix. Consistent with Θ(N²) when most bars are empty. 450 bars were cheap; 75k × 30 was not.

5. **Files changed (this task).**  
   `forex_bot/decision_quality/fast_cache.py` (new), `engine.py`, `checkpoint.py` (new), `runner.py` (new), `__main__.py`,  
   `tests/test_decision_quality_equivalence.py`, `tests/test_decision_quality_checkpoint.py`, `tests/test_decision_quality_data.py`,  
   `reports/decision_quality/research_runner_optimization.md`, `research_runner_optimization_progress.json`, `_profile_small_backtest.py`, `profile_small_eurusd_800.txt`, `_bench_optimized.py`, `bench_optimized_vs_reference.txt`, `bench_optimized_vs_reference.json`.

6. **Exact optimization implemented.** `impl="optimized"`: `SignalCache` precomputes `compute_indicators` once per lookback and closed HTF OHLC once. Per-bar path uses `iloc[:i+1]` / `iloc[i]` without prefix copies. If indicator period lengths at prefix length i+1 differ from the full frame, the prefix is recomputed so MA/ATR lengths match reference. Trade simulation is unchanged. Default engine API remains `impl="reference"`. CLI default is `--impl optimized`.

7. **Why semantics are preserved.** Same `_quant_stub_vote`, `select_strategy`, `volatility_ok`, `fx_market_open_at`, `sl_tp_from_production_distances`, spread, `bar_touches`, seeds. VOLATILITY_FILTER / FX week / session / no-strategy match `_blank` (lookback 0, empty vote, research at lookback 50). Period-tuple fallback keeps warmup identical.

8. **Lookahead protections.** Cached row i uses only bars 0..i. HTF uses period end ≤ asof (same as `resample_closed_ohlc`). Warmup still skips i < 80. No incomplete future HTF candle is exposed.

9. **Equivalence tests.** `tests/test_decision_quality_equivalence.py`: 250-bar EUR_USD goldens (decision sequence, 7 trades, SL/TP geometry, exits, HTF/regime) plus `impl="optimized"` vs reference.

10. **Equivalence results.** After matching `_blank` lookback, **5/5 passed**. Headline 800-bar bench also equivalent. Scale windows 400/800/1600/2400 trade tuples matched.

11. **Before runtime (800 bars, same slice).** REFERENCE **2.3692s** (this machine; Stage 2 original impl 4.85s including cProfile overhead).

12. **After runtime.** OPTIMIZED **0.8160s** on the same 800 bars.

13. **Speedup.** **2.90x** at 800 bars (3.79x at 400; 2.11x at 2400).

14. **Remaining bottlenecks.** Per-eval `select_strategy` + snapshot/research fields; `finalize_trade` / `observe_after_stop` `iterrows` (grows with trades × suffix). Optimized 8000 bars took 46.8s (still superlinear). Not optimized because changing those would need extra equivalence work and some are outcome-path, not the original Θ(N²) indicator/HTF loop.

15. **Baseline checkpoint architecture.** Six units `{symbol}|baseline` in canonical order. Each writes `checkpoints/baseline/{symbol}__baseline.json` immediately and updates `baseline_checkpoint.json` atomically. Prints START/FINISH + elapsed + trades.

16. **Resume behaviour.** Completed units are skipped and reloaded. A unit left `running` is redone. `--force-rerun` rebuilds the checkpoint.

17. **Checkpoint compatibility.** Resume compares schema, mode, warmup, seed, impl, session flags, SL identity, research env, combined sha256 of research+indicator/SL/TP sources, unit set, and per-symbol CSV sha256. Mismatch raises `CheckpointIncompatibleError` (CLI exit 2). No silent mix.

18. **Baseline vs ATR.** Default `--mode baseline` never runs ATR. `--mode stop_width` is explicit, 24 planned units, separate `stop_width_checkpoint.json`. Not executed on historical data.

19. **Historical inventory test.** Now requires the six downloaded M5 CSVs present, and still flags a missing required pair in an isolated temp dir.

20. **Focused test results.** Equivalence 5 passed; checkpoint 10 passed; data inventory 5 passed.

21. **Full regression.** `python -m pytest -q --tb=line` → **316 passed, 0 failed, 0 skipped** in 27.09s.

22. **Historical CSVs not modified.** No writes to `data/historical/*.csv`. `git diff HEAD` had no tracked production edits. SHA256 of the six M5 files recorded at end of task (contents unchanged by this runner work).

23. **Production trading code/behaviour not modified.** No edits to `bot_loop.py`, `trading.py`, `indicators.py`, `strategy_meta.py`, `ai_ensemble.py`, `rl_agent.py`, `oanda_exec.py`, or related live modules.

24. **Live bot/Docker not restarted.**

25. **No broker writes.** Research path has no OrderCreate/PositionClose; isolation test still passes.

26. **Total task wall-clock.** Started 2026-09-18T09:35:26Z, finished 2026-09-18T09:56:13Z → **20m 47s** (1247s).

27. **Duration of every stage.**  
    [1/10] Static performance inspection — 00m 53s  
    [2/10] Profile representative workload — 01m 00s  
    [3/10] Explain the 35-hour failure mode — 00m 44s  
    [4/10] Design the optimization — 00m 20s  
    [5/10] Equivalence tests — 01m 33s  
    [6/10] Implement performance optimization — 04m 43s  
    [7/10] Baseline checkpoint / resume — 01m 39s  
    [8/10] Separate baseline from experiments — 01m 00s  
    [9/10] Fix stale historical inventory test — 00m 26s  
    [10/10] Validate performance — 02m 06s  
    Final pytest — 00m 27s  

---

## VERIFIED ROOT CAUSE

Per-bar full-prefix indicator + HTF work (Θ(N²) when bars are empty), multiplied by 30 sequential full replays, with no incremental persist.

## OPTIMIZATIONS IMPLEMENTED

Causal indicator/HTF precompute (`impl="optimized"`), no per-bar prefix copy, period-tuple-safe fallback, baseline-only checkpointed runner.

## SEMANTIC EQUIVALENCE

YES on locked 250-bar goldens and 400–2400 bar trade tuples. Reference path kept.

## PERFORMANCE RESULTS

800-bar: 2.3692s → 0.8160s (**2.90x**), equivalent. 8000-bar optimized: 46.8s. Linear six-symbol year ~44 min; remaining path still superlinear.

## CHECKPOINT / RESUME DESIGN

Six `{symbol}|baseline` units, atomic per-symbol JSON + checkpoint, identity-guarded resume. ATR is a separate mode.

## TEST RESULTS

Focused: equivalence 5, checkpoint 10, inventory 5. Full suite: **316 passed, 0 failed**.

## REMAINING LIMITATIONS

- Offline engine still omits RL and API voters (intentional).
- `hash(symbol)` in bar seeds is process-hash-randomized (pre-existing; not changed).
- Post-stop `iterrows` and per-bar `select_strategy` still superlinear.
- Optimized default is CLI-only; library default remains `reference`.

## READY FOR SIX-PAIR BASELINE: YES

Measured 8000-bar optimized EUR_USD finished in 46.8s with equivalent smaller-window results. Linear scale of that measurement is ~7 min/symbol and ~44 min for six sequential symbols. Even if remaining superlinear trade-sim cost stretches that to a few hours, that is a reasonable checkpointed next operation versus the previous 35-hour silent 30-run job. Resume will skip completed symbols.

**The six-pair 12-month baseline was not started. ATR experiments were not started. The RL random-gate experiment was not started.**
Wait for human review before running the 12-month baseline.
