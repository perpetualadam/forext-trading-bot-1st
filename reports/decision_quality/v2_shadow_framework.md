# V2 directional shadow framework

RESEARCH / OBSERVE ONLY. V2 has zero execution authority. It cannot create, close, or modify OANDA orders, cannot change production BUY/SELL, sizing, ATR, SL/TP, profit protection, portfolio caps, USD-direction guards, reconciliation, or RL. Default action is **SKIP** (`NO_VALIDATED_DIRECTIONAL_MODEL`). No directional model was implemented.

Machine-readable store (when enabled): `data/research/v2_shadow/observations.jsonl` and `outcomes.jsonl`. Separate from production trade rows. No database migration.

---

## CURRENT PRODUCTION DECISION PATH

Frozen map: `forex_bot/decision_quality/live_path.py`. Live `evaluate()` in `forex_bot/bot_loop.py`:

1. **Candidate / market data.** M5 OHLCV (`HYBRID_OHLCV_COUNT`), last close as `price`, cycle `pricing_snapshot()` bid/ask.
2. **Open-risk first.** Manage existing positions (SL/TP vs manage price, profit protection, weekend flatten). New entries are not considered until this finishes.
3. **Entry gates.** `pre_trade_entry_blocked_reason` (reconcile / operational). Session / weekend flatten block *new* opens only.
4. **Route.** `compute_indicators(route_lookback)` → `select_strategy(symbol, df_route)` → strategy **label** + lookback + horizon (`scalp|swing|legacy`). The name does **not** set BUY/SELL.
5. **Indicators for the chosen lookback.** `compute_indicators(lookback)`, `volatility_ok`, `seq_model`, `compute_nn_pred`.
6. **Quant / ensemble direction.** `ai.vote(...)`. Default live path is `_quant_stub_vote`: SMA fast vs slow + `|returns| > STUB_MOMENTUM_THRESHOLD` + `ATR > 0`. Optional API voters join only when keys/mode are configured (`ENSEMBLE_MODE`).
7. **Final allow.** If `ai_decision["allow"]` is false, `evaluate()` returns. No new order.
8. **RL gate.** `rl_agent.decide(state)` where `state = f"{round(trend,4)}_{round(vol,6)}"`. SKIP blocks. BUY/SELL must **match** the AI side; RL cannot flip.
9. **V2 shadow (this task).** After `rl_agent.decide`, before SKIP/mismatch returns. Observe + persist if `V2_SHADOW_ENABLED`. Return discarded. Exceptions logged and ignored.
10. **Authorization / sizing.** Confidence, `sl_tp_distance_for_entry`, `position_sizing`, notional / risk / USD-direction guards.
11. **OrderCreate becomes possible** only later, after `open_fill_path` says live/paper broker and dedicated entry geometry (`fetch_entry_pricing`) succeeds. Then `oanda_exec.execute_oanda_market_open` → OANDA `OrderCreate`.

**Where BUY/SELL is selected:** `_quant_stub_vote` (and optional API voters aggregated by `AIEnsemble.vote`). Not `select_strategy`.

**What already exists at that moment:** M5 indicators (SMA, ATR, RSI, MACD, Bollinger when columns exist), last close, cycle bid/ask, pip size, hour/dow, account summary NAV/positionValue, open position map, RL action / Q / epsilon.

**What is already persisted in production:** trade rows, diagnostics (including live `mfe_pips` / `mae_pips` after a fill). RL vetoes were **not** persisted before this framework.

V2 does **not** sit on the path from step 10 onward. Its return never becomes `direction`, units, SL, TP, or an order payload.

---

## EXISTING V2 CODE FOUND: NO

No live V2 shadow contract, observer, store, scorer, or `V2_SHADOW_ENABLED` hook existed.

Offline **quant_v2** research artifacts exist and were **not** reused as a live framework (they are batch experiments, not an observe-only runtime):

| Artifact | Role |
|---|---|
| `reports/decision_quality/quant_v2_research_plan.md` | Research plan |
| `quant_v2_experiment_a`–`d` | Offline spread/volume, cross-pair, M1 path, schedule proximity |
| `quant_v2_pit_consensus_*` / `quant_v2_fxmacrodata_*` | PIT consensus / vendor probes |
| `forex_bot/decision_quality/` | Isolated historical engine (forbidden from `OrderCreate`) |

Those scripts do not observe live candidates and must not be wired into `evaluate()`. This task adds a new package: `forex_bot/v2_shadow/`.

---

## V2 OBSERVATION POINT

```
production candidate (AI allow)
       |
       +------> CURRENT PRODUCTION PATH (RL gate → sizing → geometry → OrderCreate)
       |
       +------> V2 SHADOW (after rl_agent.decide, before SKIP / mismatch return)
                    |
               record only
                    |
               NO EXECUTION
```

Hook: `bot_loop.evaluate` immediately after `rl_action = rl_agent.decide(state)`, inside `try/except` that logs `[V2 SHADOW] observe failed (ignored)` and continues.

Why this point:

- A genuine production candidate exists (`allow` already true; stub side assigned).
- RL action / Q / epsilon / state are already computed, so they can be recorded without changing RL.
- SKIP and veto candidates are still observed (needed to judge whether those skips had opportunity cost).
- The helper return is discarded. Production then uses the **same** `rl_action` / `direction` as before.

Enabled / disabled / crash / missing data: production authorization is unchanged. Position management, reconciliation, and exits run **before** this hook and cannot be blocked by it.

Default flag: unset / empty / `false` → no write, no log spam. `V2_SHADOW_ENABLED` only turns observation on. There is **no** `V2_LIVE_ENABLED`.

---

## V2 DECISION CONTRACT

`V2ShadowDecision` (`forex_bot/v2_shadow/contract.py`):

| Field | Notes |
|---|---|
| `decision_id` | `v2sh_` + SHA-256 of `timestamp\|symbol\|model\|version\|production_side` |
| `timestamp_utc` | ISO-8601 UTC at observe time |
| `symbol` | Instrument |
| `candidate_source` | Default `production_quant_stub` |
| `strategy_label` | Production `select_strategy` name (route, not side) |
| `market_price_reference` | Mid / last close already in `evaluate` |
| `proposed_action` | `BUY` \| `SELL` \| `SKIP` |
| `direction_probability_up/down` | `None` until a real model exists |
| `confidence` | `None` until a real model exists |
| `model_name` / `model_version` / `feature_schema_version` | Versioned; default `v2_none` / `0` / `v2_shadow_input_v1` |
| `reason_codes` | Default `NO_VALIDATED_DIRECTIONAL_MODEL` |
| `data_available` / `data_missing` / `data_not_computed` | From PIT cells |
| `shadow_only` | Must stay `true` (constructor rejects `false`) |
| `inputs` | Point-in-time snapshot |
| `fundamentals` | Empty slots |
| `provenance` | Empty list |
| `rl` | Read-only RL fields |

`propose_action()` always returns `SKIP`. It does not copy or invert the SMA stub. No EMA/RSI/MACD voting. No trained model. Probabilities are not invented.

---

## POINT-IN-TIME INPUTS

Each input cell is `{value, status}` with `AVAILABLE` | `MISSING` | `NOT_COMPUTED`.

Recorded from values **already in** `evaluate` (no new indicator computation):

| Field | Source |
|---|---|
| production stub side | AI `direction` |
| strategy label | `select_strategy` |
| bid / ask / mid / spread | cycle `pricing_snapshot` + last close |
| pip size | existing `pip_size(symbol)` |
| ATR, ATR/price | existing `atr_v` |
| SMA fast/slow, difference, difference/ATR | existing `ma_fast` / `ma_slow` |
| RSI, MACD, Bollinger position | last row of existing indicator columns |
| ret 1/5/15/30 | existing close series (5/15/30 = 1/3/6 M5 bars) |
| hour UTC, day of week | observe clock |
| USD direction, same-USD count | existing portfolio helpers |
| broker-backed position count | in-memory `positions` |
| gross portfolio exposure | `last_account_summary` positionValue / NAV |

Explicitly **NOT_COMPUTED** (not on the live indicator frame): `adx`, `macd_signal`.

Forbidden at decision time: `forward_pips`, `forward_return`, `direction_correct`, `mfe_pips`, `mae_pips`, `net_after_cost`. `build_observation` rejects those keys in `extras`.

No future bars. No new expensive indicators. No vendor HTTP.

---

## OPTIONAL FUNDAMENTAL INPUTS

`FundamentalSlots` — slots only, all `NOT_COMPUTED`, `external_data_available=false`:

`macro_event_id`, `macro_event_type`, `official_release_time_utc`, `consensus_value`, `consensus_provider`, `consensus_asof_utc`, `actual_first_print`, `surprise_raw`, `surprise_standardized`, `consensus_revision`, `news_sentiment`, `market_implied_expectation`, `external_data_provenance`, `external_data_available`.

Not connected to Econoday, Reuters, X/Twitter, Trading Economics, Bloomberg, BLS, or the Federal Reserve.

---

## PROVENANCE MODEL

`ProvenanceSlot` fields: `provider`, `source`, `publication_time_utc`, `retrieved_at_utc`, `asof_time_utc`, `source_identifier`, `validation_status`.

Validation states: `VERIFIED_PRE_RELEASE`, `PRE_RELEASE_DATE_ONLY`, `POST_RELEASE`, `CONFLICTING`, `UNKNOWN`.

Collectors are **not** implemented. Default observation stores `provenance=[]`.

---

## STORAGE

Append-only JSONL under `data/research/v2_shadow/`:

- `observations.jsonl` — written first, at decision time
- `outcomes.jsonl` — written later by the scorer only

No Postgres / production migration. Changing `model_name` / `model_version` changes `decision_id` and appends a **new** line; old rows are not rewritten.

JSONL filenames are gitignored so live logs are not committed.

---

## OUTCOME SCORING

`score_shadow_decision` in `forex_bot/v2_shadow/score.py`. Separate object (`ShadowOutcome`). Does not mutate the decision. Does not call OANDA.

Horizons: 5 / 15 / 30 / 60 / 120 / 240 minutes.

Executable-side (research, hypothetical):

| Side | Entry | Future close |
|---|---|---|
| BUY | decision-time **ask** | later **bid_close** |
| SELL | decision-time **bid** | later **ask_close** |

Stored per side: `forward_pips`, `forward_return`, `direction_correct`, `estimated_cost` (entry spread in pips), `net_after_cost`.

`net_after_cost` equals executable-side `forward_pips` because ask→bid / bid→ask already includes the spread. Spread is **not** subtracted a second time.

`proposed_action=SKIP` still scores both sides as `skip_opportunity` (would BUY/SELL have covered cost?).

---

## MFE / MAE SCORING

Research path only, labelled `mfe_source=research_bid_ask_path`:

| Side | MFE | MAE |
|---|---|---|
| BUY | `bid_high − ask_entry` | `ask_entry − bid_low` |
| SELL | `bid_entry − ask_low` | `ask_high − bid_entry` |

Pips always. R only when a defensible risk distance exists (default `2 × ATR / pip`, research-only).

Production `Position.max_profit_pips` / `max_adverse_pips` and `diagnostics.mfe_pips` / `mae_pips` are untouched.

---

## RL OBSERVABILITY

**YES** — read-only fields already present after `rl_agent.decide`:

| Field | Source |
|---|---|
| `rl.action` | `rl_agent.decide(state)` |
| `rl.state` | existing trend/vol state string |
| `rl.agree` / `rl.veto` | derived: SKIP ⇒ veto; BUY/SELL vs production side |
| `rl.q_values` | `rl_agent.q.get(state)` if present |
| `rl.epsilon` | `rl_agent.epsilon` |

RL behaviour is unchanged (no train, seed, epsilon, Q, or gate change). If Q is missing, the cell is `null`.

---

## FAILURE ISOLATION

- Package `forex_bot/v2_shadow` must not import `oanda_exec`, `oanda_client`, `database`, `orders`, `bot_loop`, `reconciliation`, `positions`.
- Forbidden names include `execute_oanda_market_open`, `execute_trade`, `open_position`, `close_position`, `try_begin_order_submission`, `V2_LIVE_ENABLED`.
- `shadow_only=False` cannot be constructed.
- `bot_loop` never uses the V2 return value.
- Observer exceptions cannot prevent later production steps **or** earlier position management.
- Flag off ⇒ no file write.

Architectural rule: if V2 output could reach an execution path, do not connect it. This hook is one-way observe.

---

## TEST RESULTS

Focused `tests/test_v2_shadow.py` (21 tests) plus related production invariants:

| Requirement | Test |
|---|---|
| 1. Default SKIP | `test_v2_defaults_to_skip` |
| 2. Cannot produce an executable order | `test_v2_cannot_write_broker`, `test_v2_package_source_has_no_execution_names`, `test_shadow_only_cannot_be_cleared` |
| 3. Enable does not change production | `test_enabling_shadow_does_not_change_production_decision` |
| 4. Disable does not change production | `test_disabling_shadow_does_not_change_production_decision` |
| 5. Exception does not block production | `test_v2_exception_does_not_block_production` |
| 6. No future data in snapshot | `test_no_future_fields_in_decision_snapshot` |
| 7. Scoring later / separate file | `test_outcome_scoring_is_separate` |
| 8. BUY ask → future bid | `test_buy_scoring_uses_ask_to_future_bid` |
| 9. SELL bid → future ask | `test_sell_scoring_uses_bid_to_future_ask` |
| 10. Model/version persist | `test_model_version_persists` |
| 11. Missing externals do not fail | `test_missing_external_data_does_not_fail` |
| 12. Production MFE/MAE unchanged | `test_production_mfe_unchanged` |
| 13. Entry geometry unchanged | `test_entry_geometry_unchanged` |
| 14. Reconciliation unchanged | `test_reconciliation_helper_unchanged` |
| 15. Profit protection unchanged | `test_profit_protection_pip_size_unchanged` |

Also: stub independence, RL field record, ADX `NOT_COMPUTED`.

Focused + related production files: **195 passed** before the full suite.

Full suite after persistence/archive checks (`python -m pytest tests -q`): **666 passed / 0 failed / 0 skipped**.

---

## DEPLOYMENT READINESS (Docker, observe-only)

| Check | Result |
|---|---|
| `V2_SHADOW_ENABLED` passed by compose | YES (`${V2_SHADOW_ENABLED:-}`) |
| Image workdir | `/app` (`Dockerfile`) |
| Default store path in container | `/app/data/research/v2_shadow` |
| Bind mount | `./data/research/v2_shadow:/app/data/research/v2_shadow` |
| Writable | YES — `store` creates the dir; container user is root; host path is bind-mounted |
| Survives recreate/rebuild | YES — host bind mount (image does **not** `COPY data/`) |
| Execution authority | NONE |
| Default action | SKIP / `NO_VALIDATED_DIRECTIONAL_MODEL` |
| External network from `v2_shadow` | NO |
| Vendor collectors | NO |
| PIT isolation | PASS — scorer is not called from observe |
| Secrets in JSONL | stripped if a secret-shaped key appears |

Without the bind mount, JSONL lived only in the container writable layer and would be lost on recreate. That was the only persistence fix.

### Storage growth and archive

Observation is written only after AI `allow`, once per symbol per `evaluate` cycle (`TRADE_INTERVAL` default **60s**, six pairs).

Typical serialized observation is **3392 bytes** on the current schema (empty fundamental slots + RL Q triple).

| Case | Rate | Size |
|---|---|---|
| Typical (stub allow is intermittent) | tens–hundreds / day | **0.1–1 MiB/day** |
| High (stub remains allowed every cycle, 6 pairs) | 6 / min = 8,640 / day | **~28 MiB/day** (~0.85 GiB/month) |

Active file `observations.jsonl` is **renamed** (never deleted) to `observations.YYYYMMDDTHHMMSSZ.jsonl` when it exceeds `V2_SHADOW_ARCHIVE_BYTES` (default **50 MiB**). Set `0` to disable auto-archive. Operator should copy archives off-box periodically; do **not** delete research observations to reclaim space unless they have been copied.

`[V2 SHADOW]` logs one line per recorded candidate (not per-second when there is no AI-allow candidate).

---

## HOW TO ENABLE OBSERVATION (not execution)

In `.env` (optional): `V2_SHADOW_ENABLED=true`. Default is off. Docker compose passes the variable through; empty means disabled. Compose bind-mounts the shadow directory so JSONL survives rebuild.

This flag only writes JSONL + `[V2 SHADOW]` logs. It cannot place orders. Do not add a live-execution switch.

Example log:

```
[V2 SHADOW] decision_id=v2sh_… symbol=EUR_USD production_side=BUY v2_action=SKIP model=v2_none/0 confidence=None reason=NO_VALIDATED_DIRECTIONAL_MODEL
```

---

## INTENTIONAL NON-GOALS

V2 is not “find another indicator that always says BUY or SELL.” A future BUY/SELL must be earned by independently validated, out-of-sample, after-cost evidence. Until then the natural state is SKIP.

Not done in this task: directional model, deploy, Docker restart, OANDA orders, vendor collectors, production DB migration.
