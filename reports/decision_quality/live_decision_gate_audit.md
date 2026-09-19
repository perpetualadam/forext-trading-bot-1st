# Live RL/API decision-gate audit

Research-only. Production trading was not changed.

Audit started: 2026-09-17T21:41:48Z

This report is written incrementally. The 12-month historical decision-quality runner was **not** launched. Historical M5 CSVs were **not** modified. Existing `reports/decision_quality` baseline files remain the old 12-trade / 450-bar sample and are **not** 12-month results.

---

## Item 1 — Trace the exact live decision call path

**Status:** COMPLETED  
**Started:** 2026-09-17T21:41:48Z  
**Finished:** 2026-09-17T21:45:01Z  
**Elapsed:** 193s (03m 13s)  
**Tests run:** none (static source inspection only)  
**Production code changed:** no

### VERIFIED entry into the live loop

Caller chain for a new live evaluation:

1. `forex_bot/app.py` FastAPI lifespan creates `asyncio.create_task(run_bot())` (also starts `reconciliation_loop` and `health_snapshot_loop` separately; those do not open trades).
2. `forex_bot/bot_loop.py` `run_bot()` loops forever:
   - `fetch_account_summary()` (NAV / account snapshot)
   - for each `s` in `Config.SYMBOLS`: `await evaluate(s)`
   - portfolio metrics, `evolve()`, `daily_report()`
   - `asyncio.sleep(Config.TRADE_INTERVAL)`
3. `evaluate(symbol)` is the only production function that can open a **new** local/broker position.

`execute_trade` in `forex_bot/trading.py` is **not** on the new-open path. It is used from `evaluate` only when closing an existing position.

### VERIFIED actual sequence for a NEW open

The assumed research sequence (candles → indicators → strategy → quant → RL → API → consensus → risk → execute_trade → OANDA) is **wrong in several places**. VERIFIED production order:

```
app lifespan
  → run_bot()
    → fetch_account_summary()            # account snapshot; not a vote
    → evaluate(symbol)                   # one symbol at a time
      → fetch_ohlcv(symbol, "M5", N)     # N = HYBRID_OHLCV_COUNT default 200
      → record_mid(last close)
      → [if local position exists] manage SL/TP / profit protection / weekend flatten
           then return                   # cannot open a second local slot
      → in_active_session / flatten_for_weekend   # NEW-ENTRY veto only
      → pre_trade_entry_blocked_reason()          # halt / kill switch / reconcile veto
      → compute_indicators(raw, HYBRID_ROUTE_LOOKBACK default 60)
      → select_strategy(symbol, df_route)         # name + lookback + horizon label
      → compute_indicators(raw, lookback)
      → volatility_ok(df)                         # NEW-ENTRY veto
      → seq_model.update/predict + compute_nn_pred  # payload features only
      → ai.vote(payload, symbol)                  # quant stub and/or API voters TOGETHER
           → LocalLLM.predict → _quant_stub_vote  # if configured
           → each ExternalLLM.predict             # if keys present
           → allow_score + _aggregate_direction
      → if not ai_decision["allow"]: return
      → RL state = f"{round(trend,4)}_{round(vol,6)}"
      → direction = AI direction (invalid → forced "BUY")
      → rl_agent.decide(state)
           SKIP → veto
           BUY/SELL ≠ AI direction → veto
           matching BUY/SELL → continue (does not replace AI side)
      → sl_tp_distance_for_entry + position_sizing + notional/risk/USD-direction vetoes
      → open_fill_path(symbol) → broker | simulate | mid | abort_broker_disabled
      → [paper-like] paper_open_blocked_reason
      → broker: oanda_exec.execute_oanda_market_open(...)
        OR simulate: apply_latency/impact/costs
        OR mid: last close as entry
      → open_position(Position(...))              # local book
```

### Stage table

| Stage | File | Function | Caller | Important inputs | Output | BUY/SELL/HOLD semantics | Next | Enable / bypass |
|---|---|---|---|---|---|---|---|---|
| Process start | `forex_bot/app.py` | FastAPI lifespan | uvicorn | Config | tasks | none | `run_bot` | process must be running |
| Cycle | `forex_bot/bot_loop.py` | `run_bot` | app lifespan | `Config.SYMBOLS`, `TRADE_INTERVAL` | none | none | `evaluate` per symbol | — |
| Candles | `forex_bot/oanda_client.py` | `fetch_ohlcv` | `evaluate` via `asyncio.to_thread` | symbol, `"M5"`, count | DataFrame or empty | none | abort if empty | OANDA market-data REST |
| Mid cache | `forex_bot/state.py` | `record_mid` | `evaluate` | last close | state | none | — | always |
| Weekend / session | `forex_bot/session_rules.py` | `in_active_session`, `flatten_for_weekend` | `evaluate` | symbol, now | bool | veto new entries | return | `FX_SESSION_ALWAYS` / session env |
| Existing position | `forex_bot/positions.py` | `get_position` | `evaluate` | symbol | `Position` or None | if present, close-management only | return after manage | one local slot per symbol |
| Pre-trade halt | `forex_bot/execution.py` | `pre_trade_entry_blocked_reason` | `evaluate` | halt, `KILL_SWITCH`, reconcile | reason or None | veto | return | `KILL_SWITCH`, reconcile flags |
| Route indicators | `forex_bot/indicators.py` | `compute_indicators` | `evaluate` | raw M5, route lookback | df with MA/ATR/trend/vol | features only | `select_strategy` | `HYBRID_ROUTE_LOOKBACK` |
| Strategy routing | `forex_bot/strategy_meta.py` | `select_strategy` | `evaluate` | symbol, route df | `(name, lookback, horizon)` | **does not set side** | abort if None / inactive | `HYBRID_{SYMBOL}`; else legacy pool |
| Trade indicators | `forex_bot/indicators.py` | `compute_indicators` | `evaluate` | raw M5, strategy lookback | df | features only | vol check | `SCALP_LOOKBACK` / `SWING_LOOKBACK` / `DEFAULT_INDICATOR_LOOKBACK` |
| Volatility | `forex_bot/session_rules.py` | `volatility_ok` | `evaluate` | df | bool | veto | return | session/vol env |
| Sequence hint | `forex_bot/strategy_meta.py` | `SeqModel.predict` | `evaluate` | recent prices | float | **not** a side | `compute_nn_pred` | always |
| NN hint | `forex_bot/nn_pred.py` | `compute_nn_pred` | `evaluate` | price, seq_pred | float | **not** a side; live default adds noise | AI payload | `NN_PRED_MODE`; live default `noise` |
| AI ensemble | `forex_bot/ai_ensemble.py` | `AIEnsemble.vote` | `evaluate` | payload (symbol, strategy, price, MAs, returns, ATR, preds) | `{allow, confidence, direction}` | **originates / aggregates** BUY/SELL and allow | RL gate | `ENSEMBLE_MODE`, `AI_DISABLE_STUB`, API keys |
| Quant stub | `forex_bot/ai_ensemble.py` | `LocalLLM.predict` → `_quant_stub_vote` | `vote` first (local list) | MAs, returns, ATR | allow + BUY/SELL or none | originates direction + allow | aggregation | included unless stub disabled (except `ENSEMBLE_MODE=quant` forces it) |
| API voters | `forex_bot/ai_ensemble.py` | `_fill_external_voters` + `*.predict` | `vote` after locals | same payload | allow + direction | originate/alter via aggregation | aggregation | API keys / OpenAI-compat base URL |
| Consensus | `forex_bot/ai_ensemble.py` | `vote` + `_aggregate_direction` | inside `vote` | list of voter dicts | allow if weighted allow_score > 0.5; direction = conf-weighted BUY vs SELL | can flip side vs any single voter | RL | no votes → `allow=False` |
| Direction default | `forex_bot/bot_loop.py` | `evaluate` | after vote | `ai_decision["direction"]` | `"BUY"` or `"SELL"` | **invalid/missing direction becomes BUY** | RL | always |
| RL gate | `forex_bot/rl_agent.py` | `RLAgent.decide` | `evaluate` | discrete state string | `"BUY"` / `"SELL"` / `"SKIP"` | veto only; never overrides AI side | sizing | always called; no env bypass found in `evaluate` |
| SL/TP | `forex_bot/trading.py` | `sl_tp_distance_for_entry` | `evaluate` | symbol, ATR | distances | not a side | sizing | ATR/pip env |
| Sizing | `forex_bot/trading.py` | `position_sizing`, `cap_position_units` | `evaluate` | NAV, stop, symbol | units | veto if ~0 | risk caps | notional % env |
| Notional / risk / USD-dir | `forex_bot/portfolio_exposure.py` + `trading.py` | `notional_cap_decision`, `portfolio_risk_cap_exceeded`, `usd_direction_guard_decision` | `evaluate` | candidate units/side | veto | veto | fill path | cap env vars |
| Session size cut | `forex_bot/session_rules.py` | `pre_close_adjustment` | `evaluate` | symbol | bool | 50% size; veto if units < 1 | fill | session env |
| Fill path | `forex_bot/execution.py` | `open_fill_path` | `evaluate` | symbol, paper, live window | path string | not a side | broker/sim/mid | `EXECUTION_MODE`, live windows, `use_oanda_live` |
| Paper vs broker slot | `forex_bot/reconciliation.py` | `paper_open_blocked_reason` | `evaluate` | symbol | reason or None | veto paper open | broker/sim | broker-backed occupancy |
| Broker open | `forex_bot/oanda_exec.py` | `execute_oanda_market_open` | `evaluate` | symbol, units, **already-chosen** direction, SL/TP | fill tuple | executes side; does not choose it | `open_position` | `fill_path=="broker"` |
| Local book | `forex_bot/positions.py` | `open_position` | `evaluate` | `Position` | stored slot | records side | log `[AI+RL]` | always after a successful fill decision |

### What each component can do (new-open path)

| Component | Originate direction | Reverse direction | Approve | Veto | Alter confidence | Only log | Do nothing |
|---|---|---|---|---|---|---|---|
| `fetch_ohlcv` | no | no | no | empty data aborts | no | no | if empty |
| Session / weekend flatten | no | no | no | **yes** (new entries) | no | alert | — |
| Existing local position | no | no | no | **yes** (occupies slot) | no | position log | — |
| Halt / kill / reconcile | no | no | no | **yes** | no | warning | — |
| Indicators | no | no | no | no | no | no | features only |
| `select_strategy` | **no** | no | no | abort if None/inactive | no | `[HYBRID]` later | — |
| `volatility_ok` | no | no | no | **yes** | no | alert | — |
| `seq_model` / `nn_pred` | no | no | no | no | only via API if voter uses them | no | live `nn_pred` is noisy by default |
| Quant stub (`LocalLLM`) | **yes** | n/a (first origin) | **yes** (`allow`) | **yes** (`allow=False` or no-cross) | **yes** | no | if stub omitted from ensemble |
| API voters | **yes** (vote) | **yes** (via aggregation) | **yes** | **yes** (low allow weight) | **yes** | no | if no keys |
| `AIEnsemble.vote` | **yes** (aggregate) | **yes** (weighted BUY vs SELL) | **yes** (`allow_score > 0.5`) | **yes** (score ≤ 0.5 or no votes) | **yes** | no | — |
| Invalid-direction coerce | **yes** (forces BUY) | can invent BUY if AI direction missing | n/a | no | no | no | — |
| RL `decide` | **no** (executed side stays AI) | **no** | matching BUY/SELL continues | **yes** (SKIP or disagree) | no | info log | — |
| Sizing / notional / risk / USD-dir | no | no | no | **yes** | confidence used as size scalar only when notional-% sizing is off | alerts | — |
| `open_fill_path` | no | no | no | abort if broker required but disabled | no | live-window log | — |
| `execute_oanda_market_open` | no | no | no | exception → no local open | no | alerts | if not broker path |
| `execute_trade` | no | no | no | n/a on open | no | — | **not called on open** |

### VERIFIED differences from the assumed chain

1. **API voters run inside `ai.vote`, in the same step as the quant stub**, not after RL.
2. **RL runs after the full AI ensemble**, not between quant and API.
3. **Strategy names do not choose BUY/SELL.** They choose lookback/horizon and a random-weighted label from a scalp or swing pool.
4. **`execute_trade` is the close/PnL logger, not the open path.** New broker opens call `oanda_exec.execute_oanda_market_open`.
5. **If AI `direction` is not BUY/SELL, production forces BUY** before the RL gate (`bot_loop.py` around the `direction not in ("BUY", "SELL")` check).
6. **RL cannot replace or reverse the executed side.** Disagreeing RL BUY vs AI SELL (or the reverse) blocks the trade.

### Configuration that can remove or skip a stage (high level)

- `ENSEMBLE_MODE=quant` — local quant stub only (API voters not attached).
- `ENSEMBLE_MODE=api` — API voters only; if none configured, falls back to LocalLLM.
- `ENSEMBLE_MODE` hybrid (default via `normalize_ensemble_mode`) — stub unless `AI_DISABLE_STUB`, plus any configured API voters.
- `AI_DISABLE_STUB` — omits LocalLLM in hybrid; ignored when `ENSEMBLE_MODE=quant`.
- Missing API keys — those voters are not constructed.
- `HYBRID_{SYMBOL}` off — `select_strategy` uses legacy full pool + `DEFAULT_INDICATOR_LOOKBACK`.
- `KILL_SWITCH` / runtime halt / reconcile block — skip new entries before AI/RL.
- `EXECUTION_MODE=paper` — no OANDA OrderCreate; local fill after the same AI+RL decision.
- Empty OHLCV / inactive strategy / `volatility_ok` false — abort before or during AI.

RL itself has **no bypass flag in `evaluate`**. It is always invoked after a successful AI allow.

### Files inspected (Item 1)

- `forex_bot/app.py` (lifespan → `run_bot`)
- `forex_bot/bot_loop.py` (`run_bot`, `evaluate`)
- `forex_bot/ai_ensemble.py` (`vote`, `_quant_stub_vote`, `_build_default_ensemble`, `_fill_external_voters`)
- `forex_bot/strategy_meta.py` (`select_strategy`, `SeqModel`)
- `forex_bot/nn_pred.py` (`compute_nn_pred`)
- `forex_bot/rl_agent.py` (`RLAgent.decide` signature/role only)
- `forex_bot/execution.py` (`pre_trade_entry_blocked_reason`, `open_fill_path`)
- `forex_bot/oanda_exec.py` (`execute_oanda_market_open` signature)
- `forex_bot/session_rules.py` (function names only: session / vol / live window)

Deeper RL training, API prompts, and consensus truth tables are deferred to later items.

---

## Item 2 — Audit the quant directional logic

**Status:** COMPLETED  
**Started:** 2026-09-17T21:46:33Z  
**Finished:** 2026-09-17T21:48:39Z  
**Elapsed:** 126s (02m 06s)  
**Tests run:** `python -m pytest tests/test_quant_stub_mapping.py -q --tb=short` → 9 passed in 0.23s  
**Production code changed:** no (test-only addition: `tests/test_quant_stub_mapping.py`)

### VERIFIED production function

Live quant direction is `forex_bot/ai_ensemble.py` `_quant_stub_vote`, called only via `LocalLLM.predict` (and the unused twin `ExternalLLMAPI.predict`, which is not attached by `_build_default_ensemble`).

`evaluate()` builds the payload from the **second** `compute_indicators(raw, lookback=lookback)` call:

- `ma_fast` / `ma_slow` / `sma_fast` / `sma_slow` = last rolling-mean values (same numbers)
- `returns` = last `close.pct_change()` (one-bar close-to-close return)
- `atr` = last ATR
- also passed but **unused by the stub**: `symbol`, `strategy`, `nn_pred`, `seq_pred`, `horizon`, `lookback`, `hybrid`, `price` (price is used only as a fallback when both MA keys are missing)

### Exact BUY rule

**Direction = BUY** when:

`sma_fast > sma_slow + STUB_SMA_EPSILON`  
default `STUB_SMA_EPSILON = 1e-6`

`sma_*` is preferred if present; otherwise `ma_*`. Live always sends both as the same SMA values.

**`allow = True` for that BUY** only if **both**:

1. `abs(returns) > STUB_MOMENTUM_THRESHOLD` (default `0.0001`)
2. `atr > 0` and ATR is not NaN

Otherwise direction can still be `"BUY"` with `allow=False`.

### Exact SELL rule

**Direction = SELL** when:

`sma_fast < sma_slow - STUB_SMA_EPSILON`

Same `allow` conditions as BUY (`abs(returns)` and `atr > 0`). Momentum sign is **not** required to match the MA side. A down-MA with positive last-bar return still SELL-directs if `|return|` exceeds the threshold.

### Exact NO-SIGNAL rule (`direction is None`, `allow=False`, `confidence=0`)

Any of:

- MA values cannot be parsed as floats
- `sma_fast` or `sma_slow` is NaN
- `|sma_fast - sma_slow| <= STUB_SMA_EPSILON` (flat / tie)

If both MA keys are missing, both fall back to `price`, so `|fast-slow|=0` → NO SIGNAL.

This is distinct from **directional-but-blocked**: MA separated, but weak momentum or non-positive ATR → `direction` is BUY/SELL and `allow=False`.

### Indicators, lookbacks, normalization

| Input | Source | Calculation | Lookback |
|---|---|---|---|
| `ma_fast` / `sma_fast` | `compute_indicators` | SMA of `close` (`rolling.mean`), **not** EMA | If `lookback` set: `max(3, min(lookback//10, cap))`. If `lookback is None`: 5. Live always passes a lookback. |
| `ma_slow` / `sma_slow` | same | SMA of `close` | If `lookback` set: `max(ma_fast_n+1, min(lookback//2, cap))`. If None: 20. |
| `returns` | `evaluate` | last `close.pct_change()` | 1 bar |
| `atr` | `compute_indicators` | mean true range | If lookback set: `max(7, min(lookback//5, min(30, cap)))`. If None: 14. |

With **defaults** (`SCALP_LOOKBACK=50`, `SWING_LOOKBACK=100`, `DEFAULT_INDICATOR_LOOKBACK=50`) and enough bars:

- scalp / legacy lookback 50 → `ma_fast_n=5`, `ma_slow_n=25`
- swing lookback 100 → `ma_fast_n=10`, `ma_slow_n=50`

**Normalization:** none. MAs compared in raw price units. Confidence = `min(1, max(0, abs(returns) * STUB_CONFIDENCE_SCALE))` with default scale `1000`.

**Unused by the stub:** RSI, MACD, Bollinger, `trend`, `volatility`, `nn_pred`, `seq_pred`, `strategy`, `horizon`.

### Tie / NaN / fallback

- Tie within epsilon → NO SIGNAL (above).
- NaN MAs → NO SIGNAL.
- Unparseable MAs → NO SIGNAL.
- Missing ATR / ATR 0 / ATR NaN → direction may still be set; `allow=False`.
- Missing / 0 returns → `allow=False` if `|returns|` is not greater than threshold.
- `returns` NaN: `float(nan or 0.0)` stays NaN (NaN is truthy); `abs(nan) > thr` is False → `allow=False`. Confidence can become NaN. Documented; not changed.

### Do strategy labels change the directional formula?

**VERIFIED: the formula does not read strategy names.**  
`trend`, `scalp`, `mean_reversion`, `swing_mean_reversion`, `swing_breakout`, `swing_trend` are ignored by `_quant_stub_vote`. Focused tests confirm identical BUY + confidence for all those labels.

**VERIFIED: strategy routing can still change the MA *inputs*.**  
`select_strategy` picks a lookback (scalp 50 vs swing 100 vs legacy 50). `compute_indicators` scales SMA windows from that lookback. Names inside the same horizon pool share the same lookback, so they do not change inputs either. Horizon (scalp vs swing), not the text label, is what changes MA periods.

### Files inspected (Item 2)

- `forex_bot/ai_ensemble.py` (`_quant_stub_vote`)
- `forex_bot/indicators.py` (`compute_indicators`)
- `forex_bot/bot_loop.py` (payload construction)
- `forex_bot/strategy_meta.py` (lookback / horizon only)
- `.env.example` (stub defaults)

---

## Item 3 — Identify final direction authority

**Status:** COMPLETED  
**Started:** 2026-09-17T21:52:53Z  
**Finished:** 2026-09-17T21:58:11Z  
**Elapsed:** 318s (05m 18s)  
**Tests run:** `python -m pytest tests/test_direction_authority.py -q --tb=short` → 6 passed in 0.14s  
**Production code changed:** no (test-only: `tests/test_direction_authority.py`)

### Answers (VERIFIED from source)

| Question | Answer |
|---|---|
| Which component ultimately controls BUY / SELL / NO TRADE? | **Side (BUY/SELL)** = `AIEnsemble.vote` → `_aggregate_direction`, then `evaluate` coerces any non-BUY/SELL to **BUY**. **NO TRADE** can be decided by many earlier and later vetoes; RL and risk gates cannot change the side, only block. |
| Does quant originate direction? | **Yes, as a vote** (`_quant_stub_vote`) when LocalLLM is in the ensemble. It is not the final side if other voters exist. |
| Does RL merely approve/reject? | **Yes.** Matching BUY/SELL continues; SKIP or opposite side blocks. |
| Can RL replace direction? | **No.** `evaluate` never assigns `direction = rl_action`. |
| Can RL reverse BUY→SELL or SELL→BUY? | **No.** Disagreement is a veto, not a flip. |
| Can API replace direction? | **Yes, via weighted aggregation** inside `vote`, before RL. An API-weighted SELL can beat a quant BUY. |
| Can API reverse direction? | **Yes, relative to quant**, by winning `_aggregate_direction`. It does not run after RL. |
| Does API only veto? | **No.** API votes contribute both `allow` weight and side weight. |
| Does disagreement create NO TRADE? | **Quant vs API:** no automatic NO TRADE; they are merged. **RL vs AI:** yes, NO TRADE. **API vs API:** merged, not a hard veto. |
| Do confidence thresholds affect direction? | Confidence is a **weight** for side and for `allow_score`. `allow` is true only if `allow_score > 0.5`. Confidence does not remap BUY↔SELL after that. After `vote`, confidence is a **size scalar** only when notional-% sizing is off. |
| Are missing components ignored? | Voters that are not constructed (no keys / stub disabled) are absent. If **zero** votes remain, `vote` returns `allow=False` (fail closed). Hybrid with no keys and stub disabled **re-adds** LocalLLM. |
| Do failures default to approval or rejection? | A single voter exception is **swallowed** (`logger.debug`) and that voter is omitted. Remaining votes decide. **All voters fail / none succeed → reject** (`allow=False`). |

### VERIFIED boolean / voting pseudocode

```
# --- AI ensemble (ai_ensemble.AIEnsemble.vote) ---
votes = []
for voter in local_llms + external_llms:
    try:
        votes.append(await voter.predict(payload))
    except Exception:
        omit voter   # not a veto by itself

if votes is empty:
    return allow=False, confidence=0, direction="BUY"   # direction unused

total_conf = sum(v.confidence)
allow_score = sum(v.confidence for v in votes if v.allow) / (total_conf + 1e-6)
allow = allow_score > 0.5

buy_w  = sum(v.confidence for v in votes if v.direction == "BUY")
sell_w = sum(v.confidence for v in votes if v.direction == "SELL")
if buy_w > sell_w: direction = "BUY"
elif sell_w > buy_w: direction = "SELL"
else:
    # first vote in list order with max confidence among BUY/SELL
    # if none, direction = "BUY"
    direction = first_highest_conf_side or "BUY"

# --- evaluate() after vote ---
if not allow:
    NO TRADE

side = ai.direction.upper()
if side not in ("BUY", "SELL"):
    side = "BUY"                 # coerce; does not come from RL

rl = rl_agent.decide(state)      # BUY | SELL | SKIP
if rl == "SKIP":
    NO TRADE
if rl in ("BUY", "SELL") and rl != side:
    NO TRADE                     # veto; side is not changed

# later vetoes (sizing, notional, portfolio risk, USD-direction,
# live-window abort, paper slot blocked, broker exception)
# can still produce NO TRADE without changing side.

EXECUTE side
```

### Authority summary

1. **Origin of a side vote:** quant stub and/or each API voter.
2. **Final executed side:** AI aggregate (confidence-weighted BUY vs SELL), with BUY as the hardcoded default for ties with no sided vote and for invalid AI direction.
3. **RL role:** same-side gate only.
4. **NO TRADE** is not a single voter: session, halt, empty AI, `allow_score ≤ 0.5`, RL skip/mismatch, size/risk/USD-dir, fill-path abort, broker failure.

### Files inspected (Item 3)

- `forex_bot/bot_loop.py` (direction coerce + RL gate)
- `forex_bot/ai_ensemble.py` (`vote`, `_aggregate_direction`)
- `forex_bot/experiment.py` (`normalize_ensemble_mode`)
- `forex_bot/rl_agent.py` (`decide` outputs only)

---

## Item 4 — Audit the RL implementation

**Status:** COMPLETED  
**Started:** 2026-09-17T21:59:23Z  
**Finished:** 2026-09-17T22:00:56Z  
**Elapsed:** 93s (01m 33s)  
**Tests run:** none (static inspection; mapping tests deferred to Item 5)  
**Production code changed:** no

### VERIFIED production implementation

| Field | Finding |
|---|---|
| Source file | `forex_bot/rl_agent.py` only |
| Class | `RLAgent` |
| Functions | `__init__`, `_ensure_state`, `decide`, `update`, `snapshot` |
| Model type | In-process **tabular 3-action bandit** (per-state Q dict). Not a neural net. |
| Library / framework | Python stdlib `random` only. No PyTorch, TensorFlow, Stable-Baselines, Gym, ONNX. None of those appear in `requirements.txt`. |
| Architecture | `q[state_string][action] = float`. Actions `("BUY", "SELL", "SKIP")`. |
| Model inputs / state | One string from `evaluate`: `f"{round(trend, 4)}_{round(vol, 6)}"` where `trend` and `volatility` are last-bar indicator columns (`ma_fast-ma_slow` and ATR). **No symbol, no timeframe, no prices, no MAs, no RSI.** |
| Model outputs | One of `"BUY"`, `"SELL"`, `"SKIP"` (Python str). No probabilities. |
| Action space | Those three strings. |
| BUY/SELL/HOLD mapping | `SKIP` is the hold/no-trade action. There is no integer 0/1/2 encoding in production. |
| Probability / confidence | None. `epsilon=0.25` is exploration probability, not a confidence score. |
| Thresholds | None beyond ε-greedy. No Q-value cutoff. |
| Loading process | **None.** `bot_loop.py` does `rl_agent = RLAgent()` at import. Empty `self.q = {}`. |
| Checkpoint / model file | **None found** in the repo (no `.pt`, `.pth`, `.pkl`, `.onnx`, joblib, zip weights). `snapshot()` is never called by `app.py` health/status. |
| Config selecting a checkpoint | **None.** `alpha` default `0.15`, `epsilon` default `0.25` are constructor kwargs; `evaluate` never overrides them. No `RL_*` env vars in this module. |
| Deterministic inference? | **No.** `random.random() < 0.25` explores uniformly; greedy ties use `random.choice(candidates)`. Unseen states have all Q=0, so greedy is also a 3-way random choice. |
| Does live operation change weights? | **Yes, in memory only.** On close, `rl_agent.update(pos.rl_state, pos.direction, pnl)` does `Q ← Q + 0.15*(pnl - Q)` for the **executed AI side** (`pos.direction`), not for `SKIP`. Restart loses the table. |

### Role in production

| Question | VERIFIED |
|---|---|
| Required? | **Yes** — `evaluate` always calls `decide` after AI allow. |
| Optional / bypassable? | **No bypass flag** in `evaluate`. |
| Advisory? | **No** — SKIP or disagreement **blocks** the open. |
| Veto-only? | **Yes** for the executed side. |
| Directional? | Output is named BUY/SELL/SKIP, but a mismatch **does not set** the trade side. |
| Something else? | Online tabular learner + 25% random gate. |

`forex_bot/backtest.py` constructs a **separate** `RLAgent()` for the `FOREX_BACKTEST=1` path. Offline decision-quality does **not** call this agent.

### Files inspected (Item 4)

- `forex_bot/rl_agent.py` (entire file)
- `forex_bot/bot_loop.py` (construct, `decide`, `update`)
- `forex_bot/backtest.py` (separate instance)
- `forex_bot/app.py` (no RL snapshot)
- `requirements.txt`
- repo glob for weight/checkpoint files (none)

---

## Item 5 — Verify RL action mapping

**Status:** COMPLETED  
**Started:** 2026-09-17T22:02:05Z  
**Finished:** 2026-09-17T22:03:54Z  
**Elapsed:** 109s (01m 49s)  
**Tests run:** `python -m pytest tests/test_rl_action_mapping.py -q --tb=short` → 5 passed in 0.03s  
**Production code changed:** no (test-only: `tests/test_rl_action_mapping.py`)

### VERIFIED mapping

Production does **not** use integer codes such as `0=HOLD, 1=BUY, 2=SELL`.

`RLAgent.decide` returns one of the strings `"BUY"`, `"SELL"`, `"SKIP"` from `_ACTIONS = ("BUY", "SELL", "SKIP")`.

There is no encode/decode layer, no argmax over a neural logit vector, no softmax, and no probability vector.

| Path | Mapping |
|---|---|
| Exploration (`random.random() < 0.25`) | `random.choice(("BUY", "SELL", "SKIP"))` |
| Greedy | `max(Q values)` then `random.choice` among actions sharing that max |
| Unseen state (all Q=0) | greedy tie → uniform among all three |
| `update(state, action, reward)` | writes `Q[action]` only if `action` is exactly one of those three strings |

### BUY↔SELL inversion

**VERIFIED: no inversion in `decide` or `update`.**  
Raising `Q["BUY"]` and setting `epsilon=0` yields `"BUY"`. Same for SELL and SKIP. `update(..., "BUY", 10)` increments BUY, not SELL.

`evaluate` compares the raw strings to the AI `direction` string. It does not remap RL BUY to SELL.

### Other handling

| Case | Production behaviour |
|---|---|
| Integer output | Does not occur; `decide` never returns ints. |
| Probability mapping | None. |
| Argmax | `max` on the three Q floats; ties broken randomly. |
| Invalid `update` action (e.g. `"HOLD"`, `1`) | Ignored; no state created. |
| HOLD | Not an RL action. Ensemble HOLD is a voter direction, not RL. |
| Confidence threshold | None on RL. |
| Unexpected `decide` string | **evaluate would not veto** unless the string is `SKIP` or a BUY/SELL mismatch. Only SKIP / opposite side block. Documented; not changed. |

### Files inspected (Item 5)

- `forex_bot/rl_agent.py`
- `forex_bot/bot_loop.py` (gate comparisons)
- `forex_bot/backtest.py` (same string gate)

---

## Item 6 — RL training / checkpoint provenance

**Status:** COMPLETED  
**Started:** 2026-09-17T22:06:16Z  
**Finished:** 2026-09-17T22:09:41Z  
**Elapsed:** 205s (03m 25s)  
**Tests run:** none  
**Production code changed:** no

### Can we establish that production RL is genuinely and meaningfully trained?

**No. Provenance of a trained checkpoint cannot be established because no checkpoint exists.**

A file named "model" was not found. Existence of `forex_bot/rl_agent.py` does **not** imply offline training.

| Evidence sought | Result |
|---|---|
| Checkpoint / model file | **None** (repo glob for weights/pkl/pt/onnx empty; no `models/` / `checkpoints/` dirs) |
| Dedicated training script | **None** (only `rl_agent.py` + callers `bot_loop.py` / `backtest.py`) |
| Training metadata / logs / timestamps | **None** |
| Steps / episodes / validation metrics | **None recorded** |
| `RLAgent.snapshot()` persistence | Method exists; **never called** by app health or disk I/O |

### What training *does* exist in code (VERIFIED)

Online **per-close Q update** after a position is closed:

```
Q[state][pos.direction] ← Q + 0.15 * (pnl - Q)
```

- `state` = the entry `rl_state` string stored on the `Position`
- `pos.direction` is the **executed AI side**, not SKIP
- `pnl` = `calculate_pnl` → `pnl_account_ccy(...)` (approx account currency PnL from entry vs exit)

This starts from **all zeros** every process start. After restart, the agent is untrained again.

`FOREX_BACKTEST=1` (`backtest.py`) uses a **fresh** `RLAgent()` for that run and also `update`s on close / EOD MTM. That is a separate in-memory table, not loaded into live.

### Requested fields

| Topic | Finding |
|---|---|
| Training data source | **UNKNOWN / none for a stored model.** Live updates use whatever trades that process actually closed. |
| Training date range | **None** for a checkpoint. Online updates = lifetime of the current process only. |
| Symbols | Live table is **not keyed by symbol**. One global `q` dict. |
| Timeframes | State does not include timeframe. Live candles are M5. |
| Episode definition | **Not defined.** One `update` per closed trade (or backtest EOD MTM). |
| Reward function | **VERIFIED:** raw close/MTM PnL in account-ccy units. No Sharpe, no shaped reward, no inventory penalty. |
| Transaction costs | **Not subtracted inside `update`.** Live broker PnL already reflects fill prices. Simulated closes may include spread/slippage in `pnl` before `update`. |
| Spread / slippage / SL/TP | Not part of the RL state. They affect `pnl` only insofar as they change the close PnL argument. |
| Offline vs online | **No offline pretrained artifact.** Live is **online in-process**. Backtest can learn within one backtest process only. |
| Does live continue learning? | **VERIFIED yes** until process exit. **VERIFIED** it does not persist. |

### Language

Do **not** conclude the gate is "bad." VERIFIED facts: empty Q at startup; 25% random actions; SKIP Q-values are never updated from live closes because `update` is called with `pos.direction` ∈ {BUY, SELL}.

### Files inspected (Item 6)

- `forex_bot/rl_agent.py`
- `forex_bot/bot_loop.py`
- `forex_bot/backtest.py` (`rl.update` on close and EOD)
- `forex_bot/trading.py` (`calculate_pnl`)
- repo search for training artifacts (none)

---

## Item 7 — RL symbol / timeframe compatibility

**Status:** COMPLETED  
**Started:** 2026-09-17T22:11:14Z  
**Finished:** 2026-09-17T22:12:22Z  
**Elapsed:** 68s (01m 08s)  
**Tests run:** none  
**Production code changed:** no

### Same model for all six pairs?

**VERIFIED yes.** `bot_loop.rl_agent` is a single module-level `RLAgent()`. `run_bot` calls `evaluate(s)` for every `Config.SYMBOLS` entry (default `EUR_USD`, `GBP_USD`, `USD_JPY`, `AUD_USD`, `USD_CAD`, `USD_CHF`). All share that one `q` dict.

### Is symbol identity in the state?

**VERIFIED no.** State is only `f"{round(trend_v, 4)}_{round(vol_v, 6)}"`. `decide(state)` never receives the symbol.

### Did training cover all six symbols?

**There is no offline multi-symbol training run to inspect.**  
Online updates from whichever symbols that process closed are written into the **same** table. Coverage is therefore "whatever closed in this process," not a designed six-pair training set.

### Is timeframe / horizon in the state?

**VERIFIED no.** Live OHLCV is always `"M5"` in `evaluate`. Horizon (`scalp`/`swing`/`legacy`) is not part of `state`. Two horizons that produce the same rounded trend/vol share Q-values.

### Cross-pair application without normalization

**VERIFIED:** `trend` and `volatility` are in **raw price units** (`ma_fast - ma_slow` and ATR). There is no pip normalization, no JPY-specific scale, no symbol embedding.

Consequences that are facts, not performance claims:

- USD_JPY ATR/trend magnitudes are typically orders larger than EUR_USD, so their **state strings usually differ** and occupy different keys.
- EUR_USD and GBP_USD (and other similar-scale pairs) **can share a Q row** if rounded trend/vol collide.
- A Q-value learned from one pair's close PnL is reused for any later symbol that hashes to the same string.

### Files inspected (Item 7)

- `forex_bot/bot_loop.py` (`rl_agent` singleton, M5 fetch, state format)
- `forex_bot/symbols.py` (`DEFAULT_FOREX_SYMBOLS`)
- `forex_bot/config.py` (`Config.SYMBOLS`)
- `forex_bot/rl_agent.py` (`decide` signature)
- `forex_bot/indicators.py` (`trend` / `volatility` units)

---

## Item 8 — RL feature compatibility / training–live drift

**Status:** COMPLETED  
**Started:** 2026-09-17T22:14:44Z  
**Finished:** 2026-09-17T22:16:22Z  
**Elapsed:** 98s (01m 38s)  
**Tests run:** none  
**Production code changed:** no

### Every feature passed to RL during LIVE inference

`RLAgent.decide` takes a **single string**. `evaluate` builds it as follows (VERIFIED):

| # | Name | Calculation | Source | Timeframe | Scaling / normalization | Expected range | Missing values |
|---|---|---|---|---|---|---|---|
| 1 | `trend_v` | last `df["trend"]` = `ma_fast - ma_slow` (SMA difference, price units) | `compute_indicators` after strategy lookback | Live series is M5; MA windows depend on lookback (Item 2) | none; then `round(..., 4)` | unbounded; majors typically ~1e-5–1e-3; JPY larger | NaN → `0.0` |
| 2 | `vol_v` | last `df["volatility"]` = `atr` (price units) | same | M5 ATR window from lookback | none; then `round(..., 6)` | ATR > 0 when defined; JPY larger than majors | NaN → `0.0` |

Joined as `f"{round(trend_v, 4)}_{round(vol_v, 6)}"`.

**Not passed to RL (VERIFIED):** symbol, horizon, strategy name, OHLC, RSI, MACD, Bollinger, `nn_pred`, `seq_pred`, returns, MA levels themselves, spread, session, account, positions, pip size.

### Comparison with a training feature pipeline

**There is no separate training feature pipeline.**  
Online `update` uses `pos.rl_state`, which was stored at entry from the same formula. `backtest.py` copies the same two-line construction.

Therefore:

| Drift hypothesis | Classification |
|---|---|
| RSI 0–1 vs 0–100 | **NOT APPLICABLE** — RSI is not an RL feature |
| Feature ordering difference | **NOT APPLICABLE** — one string, fixed order `trend_vol` |
| Feature-count difference | **NOT APPLICABLE** — always two rounded numbers |
| Missing/defaulted features | **VERIFIED:** NaN trend/vol become `0.0_0.0` (shared bucket) |
| Changed indicator definitions vs a stored trainer | **NOT ENOUGH EVIDENCE** of a second definition — only one `compute_indicators` |
| Lookback change vs a stored trainer | **NOT ENOUGH EVIDENCE** of a frozen trainer; live lookback is current `select_strategy` |
| Pip-scale / EUR scaling on JPY | **VERIFIED** raw price units, no pip convert (compatibility fact; not a train-vs-live file mismatch) |
| Timeframe mismatch train vs live | **NOT ENOUGH EVIDENCE** of a trained-other-TF model; live is M5 |

### VERIFIED MISMATCH

**None** between a distinct offline trainer and live inference, because no distinct trainer/feature snapshot exists.

### POSSIBLE MISMATCH (same codebase, different *inputs*)

- Scalp vs swing lookbacks change SMA/ATR windows, so the same market moment can produce different state strings across horizons.
- Process restart resets Q while the feature formula stays the same (not feature drift; policy drift to uniform random).

### Files inspected (Item 8)

- `forex_bot/bot_loop.py` (state construction)
- `forex_bot/indicators.py` (`trend`, `volatility`)
- `forex_bot/rl_agent.py`
- `forex_bot/backtest.py` (same state formula)

---

## Item 9 — Identify all API / model voters

**Status:** COMPLETED  
**Started:** 2026-09-17T22:16:43Z  
**Finished:** 2026-09-17T22:18:18Z  
**Elapsed:** 95s (01m 35s)  
**Tests run:** none (no real API calls)  
**Production code changed:** no

Secrets: no key/token values are recorded. Workspace `.env` was checked for **presence only**. The running Docker live process env was **not** inspected (UNKNOWN).

### Voters that exist in production code

#### A. Local quant stub (not an HTTP API)

| Field | Value |
|---|---|
| Provider | in-process `_quant_stub_vote` |
| File | `forex_bot/ai_ensemble.py` |
| Function | `LocalLLM.predict` |
| When called | First loop in `AIEnsemble.vote` if LocalLLM is in `local_llms` |
| Inputs | same payload as `evaluate` (Item 1) |
| Response | `{allow, confidence, direction}` |
| BUY/SELL/HOLD | Item 2; `direction=None` on no-cross |
| Confidence | `min(1, abs(returns)*STUB_CONFIDENCE_SCALE)` |
| Threshold | MA epsilon + momentum + ATR for `allow` |
| Timeout / retry | none |
| Deterministic | **Yes** (given payload + env stub knobs) |
| Approve / veto / reverse | Yes as a vote; cannot reverse after aggregation except by weight |
| Confirm-only? | No — originates side |

`ExternalLLMAPI` in the same file also calls `_quant_stub_vote`. **VERIFIED never constructed** (`ExternalLLMAPI(` has no callers).

#### B. OpenAI-compatible HTTP voter (shared class)

| Field | Value |
|---|---|
| Provider | `OpenAIVoter` — POST `{base}/chat/completions` |
| File | `forex_bot/openai_voter.py` |
| Function | `OpenAIVoter.predict` |
| When called | `vote` external loop, if instance was appended by `_fill_external_voters` |
| Inputs | full `evaluate` payload JSON in the user message + system prompt (Item 10) |
| Response format | model text parsed as JSON `{allow, confidence, direction}` |
| BUY/SELL/HOLD | `direction` uppercased; **anything other than BUY/SELL becomes BUY** |
| Confidence | float, default 0.5, clamped 0–1 |
| Allow | `bool(parsed.get("allow", False))` — missing → False |
| Threshold | none beyond ensemble `allow_score > 0.5` |
| Timeout | `OPENAI_TIMEOUT` default **60s** (per instance; other brands still use this default unless ctor overrides) |
| Retry | **none** (one POST; exception raised to `vote`, voter omitted) |
| Deterministic | **No** at default `OPENAI_TEMPERATURE=0.2`. Temperature is sent. |
| Approve / veto / reverse | Yes as a vote (allow weight + side weight) |
| Confirm-only? | Prompt asks for its own direction; payload includes strategy/price/hints but **not** a prior ensemble decision (quant result is not a separate field). See Item 10. |

**Instances that `_fill_external_voters` can append** (each is a separate vote):

| Attach condition | base_url default | model default |
|---|---|---|
| `OPENAI_API_KEY` non-empty **or** `OPENAI_BASE_URL` set to a non-`api.openai.com` host | `OPENAI_BASE_URL` or `https://api.openai.com/v1` | `OPENAI_MODEL` or `gpt-4o-mini` |
| `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1` | `DEEPSEEK_MODEL` or `deepseek-chat` |
| `MISTRAL_API_KEY` | `https://api.mistral.ai/v1` | `MISTRAL_MODEL` or `mistral-small-latest` |
| `XAI_API_KEY` or `GROK_API_KEY` | `XAI_BASE_URL` or `https://api.x.ai/v1` | `GROK_MODEL` / `XAI_MODEL` or `grok-2-latest` |
| `GROQ_API_KEY` | `https://api.groq.com/openai/v1` | `GROQ_MODEL` or `llama-3.3-70b-versatile` |
| `VENICE_API_KEY` | `VENICE_BASE_URL` or `https://api.venice.ai/v1` | `VENICE_MODEL` or `venice-uncensored` |
| `QROK_API_KEY` **and** `QROK_BASE_URL` | `QROK_BASE_URL` | `QROK_MODEL` or `default` |

#### C. Anthropic voter

| Field | Value |
|---|---|
| Provider | Anthropic Messages API |
| File | `forex_bot/anthropic_voter.py` |
| Function | `AnthropicVoter.predict` |
| When | `ANTHROPIC_API_KEY` non-empty |
| Inputs | same payload JSON + system prompt |
| Response | concatenate `content[].text`, `json.loads` |
| BUY/SELL/HOLD | same coerce-to-BUY as OpenAI voter |
| Confidence | same clamp, default 0.5 |
| Timeout | `ANTHROPIC_TIMEOUT` else `OPENAI_TIMEOUT` else 60s |
| Retry | none |
| Deterministic | **UNKNOWN** — request body does **not** set `temperature` |
| Approve / veto / reverse | Yes as a vote |

### When they are called

Only from `evaluate` → `ai.vote` (and the `FOREX_BACKTEST=1` mirror). Not from reconcile, sizing, or OANDA.

`ENSEMBLE_MODE=quant` → **no** `_fill_external_voters` (API voters not attached).  
`ENSEMBLE_MODE=api` → APIs only; if none, fallback LocalLLM.  
`hybrid` → stub unless `AI_DISABLE_STUB`, plus any configured APIs.

### This workspace `.env` (not Docker)

| Setting | Presence / value |
|---|---|
| All listed `*_API_KEY` / `OPENAI_BASE_URL` / `QROK_BASE_URL` | **unset_or_empty** |
| `ENSEMBLE_MODE` | `quant` |
| `AI_DISABLE_STUB` | `false` |

**LIKELY** (this checkout): if `ai_ensemble` is imported with this `.env`, only `LocalLLM` is attached.  
**UNKNOWN** whether the running live container has different keys/mode. That container was not opened.

### Files inspected (Item 9)

- `forex_bot/ai_ensemble.py`
- `forex_bot/openai_voter.py`
- `forex_bot/anthropic_voter.py`
- `.env.example` (key **names** only)
- workspace `.env` (presence / non-secret flags only)

---

## Item 10 — Audit API prompt / input structure

**Status:** COMPLETED  
**Started:** 2026-09-17T22:18:48Z  
**Finished:** 2026-09-17T22:20:12Z  
**Elapsed:** 84s (01m 24s)  
**Tests run:** none  
**Production code changed:** no

Prompts were inspected in source. They are **not** reproduced verbatim here.

### Structure (VERIFIED, both `OpenAIVoter` and `AnthropicVoter`)

1. **System role:** describes the model as a conservative risk gate for a forex demo; asks for a single JSON object with `allow` (bool), `confidence` (0–1), `direction` (`BUY` or `SELL`); prefers `allow=false` when ambiguous.
2. **User role:** the literal prefix `Context:` + `json.dumps(payload, indent=2, default=str)` + a short instruction to output that JSON.

OpenAI-compatible calls may also set `response_format: json_object` (`OPENAI_JSON_MODE` default true; Venice/Qrok can override).

### What the live payload contains (`evaluate` → `ai.vote`)

| Information | Present? |
|---|---|
| symbol | **Yes** (`symbol`) |
| timeframe | **No** dedicated field. `lookback` (int) and `horizon` (`scalp`/`swing`/`legacy`) are present. Candle TF is not named. |
| current price | **Yes** (`price` = last M5 close) |
| OHLC / candle stack | **No** |
| indicators | **Partial:** `ma_fast`, `ma_slow`, `sma_*` (same), `returns` (1-bar pct), `atr`. Not RSI/MACD/Bollinger. |
| quant direction | **No field** named quant/AI/ensemble decision |
| RL decision | **No** — RL runs **after** `vote` |
| strategy label | **Yes** (`strategy`) |
| spread | **No** |
| ATR | **Yes** |
| higher-timeframe | **No** (unless the voter infers from `horizon`/`lookback`) |
| session | **No** |
| existing positions | **No** |
| account state | **No** |
| news | **No** |
| other | `nn_pred`, `seq_pred`, `hybrid` (bool) |

### Is the model told the existing quant/RL direction before it decides?

**VERIFIED: it is not given an explicit prior vote.**  
RL has not run yet. The stub vote is a **sibling** in the same `vote()` call, not an input to the API.

**Potential confirmation dependence (not a performance claim):** the API sees the same MAs, last return, ATR, strategy name, and noisy `nn_pred` that the stub uses or that a human would use to guess the MA-cross side. That could **nudge** the model toward the same side as the stub without being told "quant says BUY." This is a structural observation only.

### Files inspected (Item 10)

- `forex_bot/openai_voter.py` (`_SYSTEM`, user message)
- `forex_bot/anthropic_voter.py` (`_SYSTEM`, user message)
- `forex_bot/bot_loop.py` (payload keys)

---

## Item 11 — Audit API failure behaviour

**Status:** COMPLETED  
**Started:** 2026-09-17T22:22:04Z  
**Finished:** 2026-09-17T22:24:29Z  
**Elapsed:** 145s (02m 25s)  
**Tests run:** `python -m pytest tests/test_api_voter_failures.py -q --tb=short` → 9 passed in 0.16s  
**Production code changed:** no (test-only: `tests/test_api_voter_failures.py`)

No real API failures were induced. Behaviour is from source + mocked HTTP.

### Ensemble wrapper (`AIEnsemble.vote`) — VERIFIED

On `predict` exception: log debug, **omit that voter**, continue.  
No retry. No fallback to a default vote object.  
If the vote list is empty afterwards: **`allow=False`** (NO TRADE). Remaining successful voters (including the quant stub) decide as usual.

### Per-voter HTTP (`OpenAIVoter` / `AnthropicVoter`) — VERIFIED

Timeout, connection error, HTTP error (including rate-limit status after `raise_for_status`), malformed JSON, empty body, missing `choices`/`content`: **`predict` raises**. Ensemble then ignores that voter.

There is **no in-voter retry** and **no in-voter default allow=True**.

### Table

| Case | Voter `predict` | Ensemble | Trade outcome if this is the only remaining voter | Trade outcome if quant stub still succeeded |
|---|---|---|---|---|
| Timeout | raises | omit | **NO TRADE** (`allow=False`) | stub result only |
| Exception / unavailable | raises | omit | **NO TRADE** | stub result only |
| Rate limit HTTP error | raises | omit | **NO TRADE** | stub result only |
| Malformed JSON | raises | omit | **NO TRADE** | stub result only |
| Empty output | raises | omit | **NO TRADE** | stub result only |
| Unknown / HOLD / WAIT direction | **does not raise**; direction **coerced to BUY** | counts as BUY vote | allow from JSON; **side BUY** | BUY weight added vs stub |
| Missing `allow` key | `allow=False` | counts | usually NO TRADE unless other allows | stub allow + this side weight |
| Low confidence | used as small weight | counts | `allow` still from JSON bool; score may fail `> 0.5` if mixed | smaller influence |
| Contradictory vs quant | normal vote | weighted merge | API side can win | **not** automatic NO TRADE |
| `ENSEMBLE_MODE=quant` | API not called | n/a | n/a | stub only |
| All voters fail | — | empty list | **NO TRADE** | n/a |

Does production default to quant on API failure? **Only if the stub is already in the ensemble** (hybrid/quant). It does **not** dynamically add the stub after an API failure. `ENSEMBLE_MODE=api` with a single failing API → **NO TRADE**, not a late quant fallback.

Does production default to RL? **No.** RL is not consulted if `allow=False`.

### Files inspected (Item 11)

- `forex_bot/ai_ensemble.py` (`vote` try/except)
- `forex_bot/openai_voter.py`
- `forex_bot/anthropic_voter.py`

---

## Item 12 — Actual consensus / voting truth table

**Status:** COMPLETED  
**Started:** 2026-09-17T22:26:12Z  
**Finished:** 2026-09-17T22:26:52Z  
**Elapsed:** 40s (00m 40s)  
**Tests run:** `python -m pytest tests/test_consensus_truth_table.py -q --tb=short` → 10 passed in 0.17s  
**Production code changed:** no (test-only: `tests/test_consensus_truth_table.py`)

Production is **not** a 3-way majority of QUANT|RL|API. It is:

1. **AI merge** of however many voters are attached (`allow_score > 0.5` and confidence-weighted side).
2. **RL same-side gate** on the AI side.
3. Later risk/session/fill vetoes (not in this table).

Multiple API brands are extra columns of the same type as `API`. One API column is enough if each brand is an independent `{allow, confidence, direction}` vote.

`FAIL` = voter raised / omitted. `ABSENT` = not constructed (quant-only mode, no key, stub disabled).

### After AI, before risk (VERIFIED)

Assume each present sided vote uses confidence 0.8 unless noted. `allow_score` uses **all** confidences in the denominator, including deny votes.

| QUANT | API | AI allow | AI side | RL | FINAL (this stage) | Notes |
|---|---|---|---|---|---|---|
| BUY allow | ABSENT | yes | BUY | BUY | **BUY** | quant-only match |
| SELL allow | ABSENT | yes | SELL | SELL | **SELL** | |
| BUY allow | ABSENT | yes | BUY | SELL | **NO TRADE** | RL mismatch |
| BUY allow | ABSENT | yes | BUY | SKIP | **NO TRADE** | |
| SELL allow | ABSENT | yes | SELL | BUY | **NO TRADE** | |
| deny (dir BUY) | ABSENT | no | unused | any | **NO TRADE** | stub blocked |
| NO SIGNAL (`allow=False`, dir None) | ABSENT | no | unused | any | **NO TRADE** | |
| BUY allow | BUY allow | yes | BUY | BUY | **BUY** | |
| SELL allow | SELL allow | yes | SELL | SELL | **SELL** | |
| BUY allow | HOLD allow | yes | BUY | BUY | **BUY** | HOLD adds no side weight |
| BUY allow 0.2 | SELL allow 0.9 | yes | SELL | SELL | **SELL** | API flips side |
| BUY allow 0.2 | SELL allow 0.9 | yes | SELL | BUY | **NO TRADE** | RL still must match AI |
| BUY allow 0.8 | deny SELL 0.8 | no | SELL (unused) | any | **NO TRADE** | allow_score = 0.5 not `>` 0.5 |
| BUY allow | FAIL | yes | BUY | BUY | **BUY** | API omitted |
| FAIL | FAIL / ABSENT | no | unused | any | **NO TRADE** | fail closed |
| ABSENT | ABSENT | no | unused | any | **NO TRADE** | |
| ABSENT | BUY allow | yes | BUY | BUY | **BUY** | api-only mode |
| BUY allow | SELL allow (equal conf) | yes | **first max-conf side in list order** | must match | see `_aggregate_direction` | locals run before externals; equal 0.8 BUY then SELL → **BUY** |

HTTP voters coerce HOLD/unknown → BUY **before** this table (those rows behave as BUY votes).

Invalid AI side after vote is coerced to BUY in `evaluate` (RL then compared to BUY).

### Not shown (later veto → still NO TRADE)

Session/weekend, halt/kill/reconcile, `volatility_ok`, units≈0, notional/risk/USD-direction, `abort_broker_disabled`, paper slot blocked, OrderCreate exception.

### Files inspected (Item 12)

- `forex_bot/ai_ensemble.py`
- `forex_bot/bot_loop.py` (RL gate)

---

## Item 13 — Dead / stub / cosmetic / bypassed components

**Status:** COMPLETED  
**Started:** 2026-09-17T22:27:22Z  
**Finished:** 2026-09-17T22:28:05Z  
**Elapsed:** 43s (00m 43s)  
**Tests run:** none  
**Production code changed:** no

Callers were traced; filenames were not trusted.

| Component | Classification | Evidence |
|---|---|---|
| `ExternalLLMAPI` | **Never constructed** | Class exists; `ExternalLLMAPI(` has **zero** call sites. `predict` is a second copy of the quant stub. |
| `RLAgent.snapshot` | **Never called** | Defined; no app/health/disk caller. |
| HTTP API voters | **Bypassed by configuration** when `ENSEMBLE_MODE=quant` (this workspace `.env`) or when no keys | `_build_default_ensemble` does not call `_fill_external_voters` in quant mode. Docker live env UNKNOWN. |
| `LocalLLM` / `_quant_stub_vote` | **Stub name, live-used** | Not cosmetic when attached. It **is** the directional voter in quant mode. |
| Strategy labels (`trend`, `swing_*`, …) | **Cosmetic for direction**; **live for lookback/horizon pool** | Stub ignores name. `select_strategy` still picks lookback and a random-weighted label. |
| `seq_model` / `compute_nn_pred` | **Unused by quant stub**; **payload-only for APIs** | Always computed in `evaluate`. Live default `nn_pred` is **random noise** around price. With quant-only ensemble they **do not change BUY/SELL**. |
| MICRO_STRATEGY / LOT_SIZE hook | **Dead (commented out)** | `bot_loop.py` commented block. |
| `is_live_trading(..., use_scalp_window=True)` | **Bypassed** | Commented; live calls `is_live_trading(symbol)` without scalp override. |
| RL Q-table at process start | **Placeholder policy** | Empty table + ε=0.25 + all-zero greedy tie → effectively **random BUY/SELL/SKIP** until closes update Q. Not a constant approver. |
| `SKIP` Q-values | **Never trained online** | `update` uses `pos.direction` ∈ {BUY, SELL} only. |
| Invalid-direction → BUY (ensemble voters + `evaluate`) | **Hardcoded default**, not a learned voter | Can invent BUY. |
| Offline `decision_quality` RL/API | **Intentionally not live** | Research runner omits them; not a live bypass. |

**Not dead (do affect entries):** `evolve()` can set `strat.active = False` after poor Sharpe; `select_strategy` then skips inactive names. Session, vol, reconcile, sizing, USD-direction, fill path.

**Not random as a constant voter:** quant stub is deterministic. API voters are stochastic if attached. Strategy **name** pick is random-weighted. RL explore/tie is random.

### Files inspected (Item 13)

- `forex_bot/ai_ensemble.py`
- `forex_bot/bot_loop.py`
- `forex_bot/nn_pred.py`
- `forex_bot/rl_agent.py`
- `forex_bot/strategy_meta.py`
- `forex_bot/session_rules.py` (`use_scalp_window`)

---

## Item 14 — Configuration audit

**Status:** COMPLETED  
**Started:** 2026-09-17T22:31:00Z  
**Finished:** 2026-09-17T22:31:21Z  
**Elapsed:** 21s (00m 21s)  
**Tests run:** none  
**Production code changed:** no

Secret values are not listed. Credentials: **configured=true/false** from this workspace `.env` only. Docker live process: UNKNOWN.

### Settings that affect quant / RL / API / consensus / fallback

| SETTING | DEFAULT (if unset) | CURRENT EFFECT (this workspace `.env`) | CODE LOCATION |
|---|---|---|---|
| `ENSEMBLE_MODE` | `hybrid` (`quant_only`/`stub`/`baseline`→quant; `api_only`/`llm`→api) | **`quant`** — LocalLLM only; `_fill_external_voters` not called | `experiment.normalize_ensemble_mode`, `ai_ensemble._build_default_ensemble` |
| `AI_DISABLE_STUB` | off | **`false`** — stub allowed; ignored anyway in quant mode (quant always forces LocalLLM) | `ai_ensemble._stub_disabled` |
| `STUB_SMA_EPSILON` | `1e-6` | unset → default | `_quant_stub_vote` |
| `STUB_MOMENTUM_THRESHOLD` | `0.0001` | unset → default | `_quant_stub_vote` |
| `STUB_CONFIDENCE_SCALE` | `1000` | unset → default | `_quant_stub_vote` |
| `STUB_ALLOW_THRESHOLD` / `STUB_CONFIDENCE_MIN` / `MAX` | n/a | **removed** — not read | `.env.example` comment only |
| `NN_PRED_MODE` | live: noise; backtest: seq | unset in `.env` check not done this item; code default applies | `nn_pred.compute_nn_pred` |
| `FOREX_BACKTEST` | off | not a live-gate flag | `nn_pred`, ensemble warning text |
| `OPENAI_API_KEY` | empty | **unset_or_empty** | `_openai_compat_enabled`, `OpenAIVoter` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | **unset_or_empty** — non-empty non-openai host would enable voter without a key | `_openai_compat_enabled` |
| `OPENAI_MODEL` | `gpt-4o-mini` | n/a if voter off | `OpenAIVoter` |
| `OPENAI_JSON_MODE` | true | n/a if voter off | `OpenAIVoter` |
| `OPENAI_TIMEOUT` | 60 | also Anthropic fallback | both voters |
| `OPENAI_TEMPERATURE` | 0.2 | n/a if voter off | `OpenAIVoter` |
| `ANTHROPIC_API_KEY` | empty | **unset_or_empty** | `_fill_external_voters` |
| `ANTHROPIC_MODEL` / `BASE_URL` / `MAX_TOKENS` / `TIMEOUT` / `VERSION` | see Item 9 | unused if key empty | `anthropic_voter.py` |
| `DEEPSEEK_API_KEY` + `DEEPSEEK_MODEL` | empty / `deepseek-chat` | key **unset** | `_fill_external_voters` |
| `MISTRAL_API_KEY` + `MISTRAL_MODEL` | empty / `mistral-small-latest` | key **unset** | same |
| `XAI_API_KEY` / `GROK_API_KEY` + `XAI_BASE_URL` + `GROK_MODEL`/`XAI_MODEL` | empty / x.ai / `grok-2-latest` | keys **unset** | same |
| `GROQ_API_KEY` + `GROQ_MODEL` | empty / `llama-3.3-70b-versatile` | **unset** | same |
| `VENICE_API_KEY` + URL/model/JSON | empty / venice.ai / `venice-uncensored` | **unset** | same |
| `QROK_API_KEY` + `QROK_BASE_URL` + model/JSON | empty | **unset**; key without URL logs warning and skips | same |
| `allow_score > 0.5` | hardcoded | not configurable | `AIEnsemble.vote` |
| RL `alpha` / `epsilon` | 0.15 / 0.25 | **no env**; always those defaults | `RLAgent.__init__`, `bot_loop.rl_agent = RLAgent()` |
| `HYBRID_{SYMBOL}` | off unless set | changes lookback/horizon → MA inputs, not formula | `strategy_meta.hybrid_enabled` |
| `SCALP_LOOKBACK` / `SWING_LOOKBACK` / `DEFAULT_INDICATOR_LOOKBACK` / `HYBRID_ROUTE_LOOKBACK` / `HYBRID_OHLCV_COUNT` / `HYBRID_ATR_SCALP_THRESHOLD` | 50 / 100 / 50 / 60 / 200 / 1.0 | affect indicator windows | `bot_loop`, `strategy_meta` |

### Combinations that completely bypass a component

| Combination | Bypassed |
|---|---|
| `ENSEMBLE_MODE=quant` | **All HTTP API voters** (not constructed) |
| `ENSEMBLE_MODE=api` and ≥1 key | **Quant stub** (unless no keys → stub fallback) |
| `ENSEMBLE_MODE=hybrid` + `AI_DISABLE_STUB` + ≥1 key | **Quant stub** |
| `ENSEMBLE_MODE=hybrid` + `AI_DISABLE_STUB` + no keys | Stub **re-enabled** (cannot actually run with zero voters) |
| Empty API keys | That brand’s voter |
| `QROK_API_KEY` without `QROK_BASE_URL` | Qrok voter |
| No `RL_*` flag | RL **cannot** be bypassed from env |

`ai = _build_default_ensemble()` runs **at import**. Changing env after process start does not rebuild voters until restart. This audit did not restart anything.

### Files inspected (Item 14)

- `.env.example`
- `forex_bot/experiment.py`
- `forex_bot/ai_ensemble.py`
- `forex_bot/openai_voter.py`
- `forex_bot/anthropic_voter.py`
- `forex_bot/nn_pred.py`
- `forex_bot/rl_agent.py`
- `forex_bot/strategy_meta.py`

---

## Item 15 — Live decision observability

**Status:** COMPLETED  
**Started:** 2026-09-17T22:34:50Z  
**Finished:** 2026-09-17T22:37:49Z  
**Elapsed:** 179s (02m 59s)  
**Tests run:** none  
**Production code changed:** no

### Can an old live trade be reconstructed as `quant=SELL, RL=SELL, API1=SELL, API2=HOLD, final=SELL`?

**VERIFIED: not exactly.** At best **partially**.

### What is stored / logged

| Surface | What is present | Per-voter votes? |
|---|---|---|
| Log `[AI+RL]` on **successful open** | symbol, **final** Dir, units, **aggregate** Conf (`allow_score`), **RL_Action**, `rl_state`, horizon, lookback | **No** |
| Log `RL decided to skip` / `RL gate blocked (rl=… ai=…)` | RL action + AI side + state | **No** quant/API split |
| `if not ai_decision["allow"]: return` | **No log** | — |
| Alert `[HYBRID]` | symbol, horizon, lookback, strategy name, route lookback | No |
| Alert `[OPEN]` | final side, units, prices, SL/TP, kind, strategy, horizon | No |
| `Position` | `direction`, `strategy_name`, `rl_state` (trend_vol string only) | No RL action persisted on the position |
| Postgres `trades` (on **close**) | time, symbol, strategy, **final** direction, pnl, size, prices, trading_mode, execution_kind, diagnostics JSON | diagnostics are **exit/MFE/SL-TP**, not votes |
| Postgres `exec_orders` | side, units, status, metadata `{mid, strategy}` (and fill slippage later) | **No** votes |
| Health / operational events | execution/reconcile, not AI votes | No |

`AIEnsemble.vote` does not persist the `votes` list.

### What is NOT stored

- Quant stub `{allow, direction, confidence}`
- Each API voter's raw JSON / `{allow, direction, confidence}`
- Number of voters / which brands ran
- Payload sent to APIs
- API request/response bodies
- `nn_pred` / `seq_pred` / MA values at decision time
- Why `allow=False` (silent return)
- RL Q-table / epsilon draw vs greedy

### Reconstruction verdict

| Question | Verdict |
|---|---|
| Final executed side of a **filled** trade | **Yes** (logs, position, `trades.direction`, `exec_orders.side`) |
| RL action on that fill | **Yes if `[AI+RL]` log retained**; **not** in DB |
| Aggregate confidence | **Yes if log retained**; not in DB |
| Quant vs each API | **No** |
| Silent AI vetoes (no trade) | **Generally no** (no log) |
| RL vetoes | **Yes if those info logs retained** |

Historical live decisions: **partial** for opens that logged `[AI+RL]`; **not at all** for the full voter tuple.

### Files inspected (Item 15)

- `forex_bot/bot_loop.py` (log lines)
- `forex_bot/trade_diagnostics.py`
- `forex_bot/database.py` (`trades`, `exec_orders`)
- `forex_bot/positions.py`
- `forex_bot/ai_ensemble.py` (`vote` return shape)

---

## Item 16 — Live vs offline decision parity

**Status:** COMPLETED  
**Started:** 2026-09-17T22:38:09Z  
**Finished:** 2026-09-17T22:40:19Z  
**Elapsed:** 130s (02m 10s)  
**Tests run:** none  
**Production code changed:** no  
**Backtester:** not modified; 12-month runner not launched.

Offline path: `forex_bot/decision_quality/signal.py` `evaluate_signal` (documented in `live_path.py`).

| COMPONENT | LIVE | OFFLINE decision-quality |
|---|---|---|
| Candles | OANDA `fetch_ohlcv` M5, last `HYBRID_OHLCV_COUNT` | Historical CSV window (mid; bid/ask if present but signal uses mid OHLC) |
| Indicators | `compute_indicators` twice (route + trade lookback) | Same functions, same lookbacks |
| Strategy routing | `select_strategy` (**unseeded** `random` / `np.random`) | Same algorithm via `seeded_select_strategy` (**fixed seed per bar**) |
| Quant stub | `_quant_stub_vote` via `LocalLLM` if attached | **Always** `_quant_stub_vote` only |
| `seq_model` / `nn_pred` | Computed; live default **noise**; unused by stub | **Not computed** in `production_quant_decision` |
| RL | Always `decide`; can veto | **Omitted** |
| API voters | If constructed (`ENSEMBLE_MODE` + keys) | **Omitted** |
| Consensus | Weighted `vote` + BUY coerce | Quant `allow` + sided direction only |
| Session logic | `in_active_session` / weekend flatten **on** for new entries | FX week **on** by default; session hours **off** by default (`apply_session_hours=False`) |
| Volatility | `volatility_ok` | Same, if `apply_volatility_filter` (default on) |
| Halt / kill / reconcile | `pre_trade_entry_blocked_reason` | **Omitted** |
| Notional / portfolio risk / USD-direction | **On** | **Omitted** |
| SL/TP distances | `sl_tp_distance_for_entry` | Same helper via `sl_tp_from_production_distances` |
| Spread | Broker fill **or** sim layers **or** mid | `simulated_half_spread` on entry |
| Entry/exit pricing | Open: broker/sim/mid. Manage: **close-only** SL/TP | Research path-aware **high/low** (intentional; `LIVE_EXIT_USES_CLOSE_ONLY` documents the difference) |
| `execute_trade` | Close/PnL log only | Not used; isolated engine |

### Known reasons offline can disagree with a live trade decision

1. **RL veto** (SKIP or opposite side) — live NO TRADE, offline may still signal.
2. **API vote** flips or blocks via `allow_score` — live differs from stub-only offline. (Workspace `.env` is `quant`, so **this checkout** would match stub; Docker UNKNOWN.)
3. **Invalid/HOLD API side coerced to BUY** — not in offline.
4. **Strategy RNG** — live unseeded vs offline seeded → different lookback/horizon → different MAs → different stub.
5. **`nn_pred` noise** — only matters if APIs are attached.
6. **Session hours** — live can skip; offline default does not apply `in_active_session_at`.
7. **Risk / USD-direction / reconcile / halt** — live veto only.
8. **Candle source / last-N vs full history scaling** — `compute_indicators` periods depend on `len(df)` / `indicator_scale_n`; live uses last 200 M5 bars, offline uses the research window (can change MA/ATR periods).
9. **Fill vs mid** — does not change **side**, can change whether size/risk caps fire and SL/TP prices.
10. **Exit model** — not an entry-side difference, but outcome stats are not live-identical.

Do **not** treat existing 12-trade / 450-bar reports as 12-month or as live-gate results.

### Files inspected (Item 16)

- `forex_bot/decision_quality/live_path.py`
- `forex_bot/decision_quality/signal.py`
- `forex_bot/decision_quality/execution_sim.py`
- `forex_bot/bot_loop.py`

---

## Item 17 — Historical replay feasibility

**Status:** COMPLETED  
**Started:** 2026-09-17T22:41:37Z  
**Finished:** 2026-09-17T22:45:41Z  
**Elapsed:** 244s (04m 04s)  
**Tests run:** none  
**Production code changed:** no  

No historical RL/API replay was implemented. No fabricated votes.

| Component | Class | Why |
|---|---|---|
| M5 mid candles (downloaded CSVs) | **A** if using those files; **B** if needing exact live last-200 OANDA snapshot | Files are deterministic. Live `evaluate` uses only the last N broker bars, whose period scaling can differ from a full-history compute. |
| Indicators / quant stub | **A** given the same OHLC window, lookback, and stub env | Pure functions. |
| Strategy routing | **B** | Algorithm is known but uses RNG. Replay needs the **historical RNG stream** or stored `(strategy, lookback, horizon)` per bar. Seeded offline is **not** the live stream. |
| `nn_pred` (live noise) | **C** unless the drawn noise was stored | `random.uniform` each call. Unused for quant-only side. |
| RL `decide` | **C** for past live ticks; **B** going forward if Q + RNG + state are snapshotted | Empty Q + ε-greedy + random ties. Past process Q is gone. Even with a checkpoint, need `random` state. |
| RL `update` / live learning | **C** historically | In-memory, not persisted. |
| API / LLM voters | **C** unless original request/response stored | Provider/model drift, temperature 0.2, network, news not in payload. **Responses were not stored.** |
| Ensemble aggregation | **A** if all voter dicts are known | Deterministic given votes. |
| Session / FX week / vol | **A** given timestamp + same env + same indicator df | `in_active_session_at` / `fx_market_open_at` / `volatility_ok` are deterministic. |
| Halt / kill / reconcile | **B** | Needs historical operational/reconcile state. |
| Sizing / notional / USD-direction | **B** | Needs NAV, open book, USD-direction counts at that time. |
| Broker fill / SL/TP on fill | **B** | Needs stored fill (or treat as C if only mid exists). |
| Live close-only SL/TP vs path | **A** if replaying **live's** close-only rule on historical closes; **C** vs actual intra-bar broker stops | Different question from entry side. |

**Do not** invent historical RL/API decisions. A future replay that only reruns quant would be an A-class **offline** signal, not a reconstruction of live gates.

### Files inspected (Item 17)

- Findings from Items 1–16 (no new production files)

---

## Item 18 — Final synthesis and regression check

**Status:** COMPLETED  
**Started:** 2026-09-17T22:46:01Z  
**Finished:** 2026-09-17T22:49:32Z  
**Elapsed:** 211s (03m 31s)  
**Production code changed:** no

### Regression command (normal suite only)

```
python -m pytest -q --tb=line
```

- **291 passed**
- **1 failed**
- **Duration:** 18.43s
- **Not run:** `python -m forex_bot.decision_quality` (12-month historical runner), historical download, RL training, broker writes

**Failure (research test, not live trading):**  
`tests/test_decision_quality_data.py::test_inventory_reports_missing_pairs`  
expects GBP_USD / USD_JPY / AUD_USD / USD_CAD / USD_CHF to have **0 bars** / "no local CSV". Those CSVs now exist from the earlier approved download (~74k bars). The assertion `74555 == 0` is that stale assumption. **Historical files were not modified. The test was not rewritten.** This is not a production decision-gate bug.

### Answers required by the audit brief

1. **Exact live decision call path.**  
   `app` lifespan → `run_bot` → `evaluate(symbol)` → M5 OHLCV → session/weekend + existing-slot + halt/reconcile → route indicators → `select_strategy` → trade indicators → `volatility_ok` → seq/nn hints → `ai.vote` (quant and/or APIs together) → RL same-side gate → SL/TP + size + notional/risk/USD-dir → `open_fill_path` → `execute_oanda_market_open` or local fill → `open_position`. `execute_trade` is **close-only**.

2. **Exact quant BUY rule.**  
   `sma_fast > sma_slow + STUB_SMA_EPSILON` (default 1e-6). `allow` also needs `|returns| > 0.0001` and `atr > 0`.

3. **Exact quant SELL rule.**  
   `sma_fast < sma_slow - STUB_SMA_EPSILON`. Same `allow` extras. Momentum **sign** need not match the MA side.

4. **Exact NO-SIGNAL rule.**  
   Unparseable/NaN MAs, or `|fast-slow| ≤ epsilon` → `direction=None`, `allow=False`. Distinct from directional-but-`allow=False` (weak momentum / ATR≤0).

5. **Which component initially originates direction.**  
   Each attached AI voter. Default/live-quant: `_quant_stub_vote`. Final **executed** side is the ensemble aggregate (then BUY-coerced if invalid).

6. **Exact RL role.**  
   Always-on same-side **gate** after AI allow. Tabular ε-greedy bandit on `trend_vol` string.

7. **Whether RL can veto.**  
   **Yes:** `SKIP` or BUY/SELL ≠ AI side.

8. **Whether RL can reverse direction.**  
   **No.**

9. **RL action mapping.**  
   Strings `BUY` / `SELL` / `SKIP`. No integer 0/1/2. No inversion.

10. **Exact production RL checkpoint/model.**  
    **None.** `RLAgent()` empty `q` at import. No weight file.

11. **Evidence whether it is meaningfully trained.**  
    **Provenance of a trained model cannot be established.** Online in-memory Q updates from close PnL only; lost on restart.

12. **RL training data/symbol/timeframe coverage.**  
    No offline dataset. One table, no symbol/TF in state. Live candles M5. Six symbols share the table.

13. **RL reward function.**  
    Raw account-ccy close/MTM PnL: `Q ← Q + 0.15*(pnl - Q)` on `pos.direction`.

14. **RL training/live feature compatibility.**  
    Same two rounded numbers; no second pipeline. **No VERIFIED MISMATCH** of trainer vs live files (no trainer).

15. **Symbol/timeframe compatibility.**  
    Shared agent; raw price units; no pip normalize; no symbol id.

16. **Every API voter and its role.**  
    Optional HTTP votes: OpenAI-compat clones + Anthropic. Workspace `.env`: **none attached** (`ENSEMBLE_MODE=quant`, keys empty). Docker UNKNOWN.

17. **API inputs/prompt structure.**  
    System JSON schema + `json.dumps(evaluate payload)`. No candle stack, news, account, positions, spread, explicit quant/RL vote.

18. **Whether API voters see the prior quant/RL decision.**  
    **No explicit prior vote.** RL runs after. Features could still correlate with the stub (structural only).

19. **API failure behaviour.**  
    Omit voter; empty list → fail closed. No retry. `api` mode does not add quant after failure. HOLD/unknown → BUY inside voter.

20. **Consensus/voting truth table.**  
    See Item 12. Weighted AI merge, then RL gate. Not 3-way majority.

21. **Component with final authority before execution.**  
    **Side:** AI aggregate (+ BUY coerce). **Go/no-go after that:** RL, then risk/fill gates.

22. **Every component capable of veto.**  
    Empty OHLCV; session/weekend; occupied slot; halt/kill/reconcile; no/inactive strategy; `volatility_ok`; AI `allow=False` / no votes; RL SKIP/mismatch; size≈0; notional; portfolio stop-risk; USD-direction; live-window abort; paper slot block; broker exception.

23. **Every component capable of reversing direction.**  
    **API voters** (via weights vs quant). **`_aggregate_direction`**. HTTP HOLD→BUY coerce. **`evaluate` invalid→BUY**. **Not RL.**

24. **Dead/stub/random/cosmetic/bypassed.**  
    See Item 13. Notable: `ExternalLLMAPI` unused; APIs off in this `.env`; `nn_pred` unused by stub; strategy names unused for side; RL random at cold start; commented MICRO_STRATEGY hook.

25. **Relevant configuration.**  
    See Item 14. Especially `ENSEMBLE_MODE=quant` here; no `RL_*` bypass; `allow_score > 0.5` hardcoded.

26. **Current live-decision observability.**  
    `[AI+RL]` final side + aggregate conf + RL action; DB final side; no per-voter records. AI deny is silent.

27. **Whether old live decisions can be reconstructed.**  
    **Partially** (final side ± log RL). **Not** the full voter tuple.

28. **Exact live-vs-offline discrepancies.**  
    See Item 16 table (RL/API/consensus/session-hours default/RNG/risk/exits/window length).

29. **Which components are historically replayable.**  
    See Item 17 (A/B/C).

30. **Bugs or suspicious behaviour discovered (not fixed).**  
    See **POTENTIAL PROBLEMS** below.

31. **Tests added.**  
    `tests/test_quant_stub_mapping.py`, `tests/test_direction_authority.py`, `tests/test_rl_action_mapping.py`, `tests/test_api_voter_failures.py`, `tests/test_consensus_truth_table.py`.

32. **Focused test results.**  
    9+6+5+9+10 = **39 passed** in those files.

33. **Final regression result.**  
    **291 passed, 1 failed** in 18.43s (`test_inventory_reports_missing_pairs` stale vs historical CSVs).

34. **Production files changed.**  
    **None.**

35. **Confirmation live trading was not changed.**  
    **Confirmed.** No edits under production trading modules. No Docker rebuild/restart. No broker orders. No RL retrain. No backtester/CSV changes. No 12-month runner.

36. **Total audit wall-clock duration.**  
    Start `2026-09-17T21:41:48Z` → finish `2026-09-17T22:49:32Z` = **4064s (67m 44s)** wall clock. Sum of item elapsed times = 2402s (gaps between items are included in wall clock only).

37. **Duration of every numbered item.**  
    See progress JSON and table below.

### Item durations (measured)

| Item | Elapsed |
|---|---|
| 1 Trace path | 193s (03m 13s) |
| 2 Quant | 126s (02m 06s) |
| 3 Authority | 318s (05m 18s) |
| 4 RL impl | 93s (01m 33s) |
| 5 RL mapping | 109s (01m 49s) |
| 6 Provenance | 205s (03m 25s) |
| 7 Symbol/TF | 68s (01m 08s) |
| 8 Features | 98s (01m 38s) |
| 9 API voters | 95s (01m 35s) |
| 10 Prompts | 84s (01m 24s) |
| 11 API failures | 145s (02m 25s) |
| 12 Truth table | 40s (00m 40s) |
| 13 Dead/stub | 43s (00m 43s) |
| 14 Config | 21s (00m 21s) |
| 15 Observability | 179s (02m 59s) |
| 16 Live vs offline | 130s (02m 10s) |
| 17 Replay class | 244s (04m 04s) |
| 18 Synthesis + pytest | 211s (03m 31s) |

---

## CRITICAL FINDINGS

1. **A live BUY/SELL is not “strategy name → side.”** Side comes from `AIEnsemble.vote`. With this workspace `.env` (`ENSEMBLE_MODE=quant`, no API keys) that is the **MA-cross + momentum stub**. Docker container env was not inspected (UNKNOWN).
2. **RL is not a directional policy in execution.** It only vetoes. It is also **not a loaded trained model**: empty in-memory Q, 25% random, unseen states random among BUY/SELL/SKIP.
3. **Offline decision-quality does not reproduce the live gate** whenever RL vetoes, APIs are attached, routing RNG differs, or live risk/session/reconcile vetoes fire.
4. **Per-voter live decisions are not stored.** Old trades cannot be reconstructed as quant/RL/API tuples.
5. **`execute_trade` is not the open path.** Broker opens are `execute_oanda_market_open`.

## VERIFIED BEHAVIOUR

- Call path in Item 1; quant rules in Item 2; authority/RL/API/consensus in Items 3–12.
- Stub ignores strategy labels; lookback/horizon can still change SMA windows.
- Ensemble fail-closed on zero votes; single voter exceptions are omitted.
- HTTP HOLD/unknown direction becomes BUY inside the voter.
- Six symbols share one RL table and one `evaluate` function; OHLCV is M5.

## POTENTIAL PROBLEMS — NOT CHANGED

These are facts / structural risks, **not** proven performance harm:

- Cold-start RL is effectively random and can veto a valid stub signal ~often (ε=0.25 plus all-zero ties).
- `SKIP` Q is never updated from live closes.
- Invalid/HOLD directions coerced to **BUY** in voters and in `evaluate`.
- `allow=False` from AI is **silent** (no log).
- `nn_pred` live noise is unused by the stub but would enter API prompts if APIs were on.
- Strategy name is random-weighted even though it does not set side.
- Equal allow vs deny confidence → `allow_score=0.5` → NO TRADE (`>` not `>=`).
- Shared Q across pairs; raw (not pip) state.
- Stale inventory test vs existing historical CSVs (research test only).

## LIVE VS OFFLINE DISCREPANCIES

See Item 16. Headline: offline = quant+routing+SL/TP+vol+FX-week; live also has RL, optional APIs, unseeded routing, more vetoes, close-only management, last-N bar scaling.

Existing `reports/decision_quality` baseline files remain the **old 12-trade / 450-bar** sample. They are **not** 12-month results.

## HISTORICAL REPLAY LIMITATIONS

See Item 17. Quant can be A-class on stored M5. Live RL and API decisions from the past are **C** without stored Q/RNG and request/response logs. Do not fabricate them.

## RECOMMENDED NEXT INVESTIGATION — NOT IMPLEMENTED

Wait for human review before any of these:

1. Confirm the **running Docker/live process** `ENSEMBLE_MODE` and whether any API keys are actually injected (boolean only).
2. Decide whether historical tests should treat six downloaded CSVs as present (update research inventory test) without touching the CSVs.
3. If live-vs-offline parity is required: specify whether to **record** live votes, **replay** stub-only, or **simulate** RL (knowing C-class limits).
4. If RL is intended to be a real policy: that would be a **new** design (persist Q, symbol features, disable ε in prod, etc.) — not done here.
5. If observability is required: persist per-voter `{allow,direction,confidence}` on each decision — not done here.

**STOP.** Live trading unchanged. No recommendations implemented.
