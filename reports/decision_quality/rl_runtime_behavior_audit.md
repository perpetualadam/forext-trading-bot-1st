# RL runtime behaviour audit

Read-only. Production trading was not changed. RL was not retrained, removed, or re-tuned. Docker was not rebuilt or restarted. No broker orders were sent. The 12-month decision-quality backtester was not run.

Written: 2026-09-18T09:26:23Z

Running container inspected: `forexttradingbot1st-bot-1` (compose service `bot`), **Up ~2 days**, image `forexttradingbot1st-bot`, created 2026-09-15 23:08:50 BST. Process `/health.started_at`: `2026-09-15T22:09:03.225991+00:00`.

---

## RUNNING CONFIGURATION

Sources: `docker compose exec` process env (secret values never printed), `GET http://127.0.0.1:8001/experiment` and `/health`, workspace `.env` key presence / non-secret values, `docker-compose.yml` passthrough list, `forex_bot/rl_agent.py`, `forex_bot/bot_loop.py`.

### Effective decision values — RUNNING CONTAINER

| Setting | Running value |
|---|---|
| `ENSEMBLE_MODE` | `quant` (confirmed by env and `/experiment.ensemble_mode`) |
| Local/quant voter | **enabled** — `/experiment.local_voters=1` |
| External API/model voters | **none attached** — `/experiment.external_voters=0` |
| OpenAI-compat voter | **disabled** (`OPENAI_API_KEY` configured=false, `OPENAI_BASE_URL` unset) |
| Anthropic | **disabled** (key configured=false) |
| DeepSeek / Mistral / xAI-Grok / Groq / Venice / Qrok | **disabled** (keys configured=false) |
| `AI_DISABLE_STUB` | `false` (ignored in `quant` mode; stub is forced on) |
| `NN_PRED_MODE` | `seq` |
| Stub SMA/momentum/confidence env | unset → code defaults `1e-6` / `0.0001` / `1000` |
| `FOREX_SYMBOLS` | six pairs |
| `EXECUTION_MODE` | `live_broker` |
| `TRADING_MODE` | `live` |
| `PAPER_TRADING` | `false` |
| `trading_allowed` | true (`/health`) |
| OANDA access token | configured=**true** (value not recorded) |
| OANDA API key alias | configured=**false** |

`ENSEMBLE_MODE=quant` means `_fill_external_voters` is **not** called even if keys were present. Keys are also empty.

### RL in the running bot

| Question | Effective value | Evidence |
|---|---|---|
| RL enabled/disabled | **Always enabled** — no env bypass | `evaluate` always calls `rl_agent.decide`; `RL_ENABLED` / `RL_DISABLE` **unset** in container |
| Epsilon | **0.25** | `RLAgent()` in `bot_loop.py` uses constructor default; `RL_EPSILON` unset |
| Alpha (learning rate) | **0.15** | same; `RL_ALPHA` unset |
| Checkpoint / model file | **none** | `RL_CHECKPOINT` / `RL_MODEL` unset; `RLAgent()` starts `self.q = {}` |
| Exploration config | hardcoded `epsilon=0.25` only | no `RL_*` env in `rl_agent.py` |
| Persist / load / save | **none** | `RL_PERSIST` / `RL_LOAD` / `RL_SAVE` unset; no save/load code |
| Seed | **none** | `RL_SEED` unset; live path does not call `random.seed` |

`/health` and `/experiment` do **not** expose `rl_agent.snapshot()`. Q-table size of the **running** interpreter was **not** read (that would require attaching to the live process).

### WORKSPACE `.env` vs RUNNING CONTAINER

Decision-relevant fields match.

| Item | Workspace `.env` | Running container | Same? |
|---|---|---|---|
| `ENSEMBLE_MODE` | `quant` | `quant` | yes |
| `AI_DISABLE_STUB` | `false` | `false` | yes |
| `NN_PRED_MODE` | `seq` | `seq` | yes |
| All listed API keys | configured=false | configured=false | yes |
| API base URLs | unset | unset | yes |
| All `RL_*` keys | unset | unset | yes |
| `FOREX_SYMBOLS` | six pairs | six pairs | yes |
| `EXECUTION_MODE` | `live_broker` | `live_broker` | yes |
| `TRADING_MODE` | `live` | `live` | yes |
| `PAPER_TRADING` | `false` | `false` | yes |
| `FOREX_BACKTEST` | `<UNSET>` | empty string | **cosmetic only** — both falsy |

No decision-gate difference was found between this `.env` and the running container env.

The running **image** still contains the same RL strings (`[AI+RL]`, skip/gate logs, `RLAgent()`, `rl_agent.update`) as current workspace source.

---

## EMPTY-TABLE BEHAVIOUR

Source: `forex_bot/rl_agent.py` `decide` / `_ensure_state`; `bot_loop.py` `rl_agent = RLAgent()`.

1. **Unseen-state Q-values**  
   `_ensure_state` inserts `{ "BUY": 0.0, "SELL": 0.0, "SKIP": 0.0 }`. VERIFIED.

2. **Action when all Q-values are equal**  
   Greedy path: `best = max(table.values())` then `candidates =` every action with that value → all three → `random.choice(candidates)`. VERIFIED.

3. **Exact action ordering**  
   `_ACTIONS = ("BUY", "SELL", "SKIP")`. Dict keys are created in that order. VERIFIED.

4. **Tie resolution**  
   Uniform `random.choice` among tied actions. Not first-wins, not argmax-stable. VERIFIED.

5. **Epsilon exploration**  
   If `random.random() < self.epsilon` (0.25): ignore Q and `random.choice(_ACTIONS)`.  
   Boundary: `random() < 0.25` — a draw of exactly `0.25` is **greedy**. VERIFIED by test.

6. **Effective epsilon in the running bot**  
   **0.25**. No container override.

7. **Is randomness seeded?**  
   **No** on the live path. `random.seed` appears in `backtest.py` and offline `decision_quality`, not in `app.py` / `bot_loop.py` / `rl_agent.py`.

8. **If seeded, where/how?**  
   Not seeded in production.

9. **If unseeded, what RNG?**  
   Python stdlib `random` (global Mersenne Twister). First use is seeded from OS entropy by the interpreter. Not `numpy`, not a per-agent RNG.

10. **Can identical market state produce different RL decisions?**  
    **Yes.** Both the ε branch and the all-zero greedy tie use `random.choice`.

11. **Can RL return BUY?**  
    **Yes.**

12. **Can RL return SELL?**  
    **Yes.**

13. **Can RL return SKIP/HOLD?**  
    **SKIP: yes.** **HOLD: no.** HOLD is not in `_ACTIONS`. `evaluate` treats `SKIP` as veto.

14. **Expected frequencies for an unseen state**  
    Explore (p=0.25) is uniform on 3 actions; greedy (p=0.75) is also uniform because all Q=0.  
    **P(BUY)=P(SELL)=P(SKIP)=1/3.**  
    Combined with the live gate: given an AI BUY, P(allow)=P(RL=BUY)=1/3; P(veto)=2/3 (SELL or SKIP). Same for AI SELL. This is implementation arithmetic, not a live frequency measurement.

15. **Does RL update Q during live operation?**  
    **Yes**, in-process only.

16. **Where?**  
    `forex_bot/bot_loop.py` after a successful close: `rl_agent.update(pos.rl_state, pos.direction, pnl)` (only if `execute_trade` did not raise).

17. **What reward?**  
    The close `pnl` (account-ccy mark-to-market / realized value from `calculate_pnl` / `execute_trade`). Not Sharpe, not pip count.

18. **When is reward supplied?**  
    After the close execution path succeeds, using the **entry** `pos.rl_state` and the **executed AI side** `pos.direction` (BUY/SELL), not SKIP.

19. **Survive process/container restart?**  
    **No.** In-memory `self.q` only. This container has been up since 2026-09-15T22:09:03Z; a restart would empty the table.

20. **Is the table ever saved?**  
    **No.** `snapshot()` is never called by `app.py`. No pickle/file write.

21. **Is an existing table ever loaded?**  
    **No.**

22. **Approximately how many entries are in the running Q-table?**  
    **UNKNOWN.** Health/status do not expose it. `docker compose exec python` would start a **new** interpreter with an empty `q`, not the live one. Attaching to PID 1 / uvicorn workers was not done (unsafe process manipulation).

---

## EPSILON / RANDOMNESS

- Production ε = **0.25**, hardcoded.
- Live `decide` is **stochastic** on every call that hits exploration **or** a Q tie.
- Unseen states are **always** a 3-way random draw (explore and greedy coincide).
- After updates, greedy can become deterministic **for that state** if one action’s Q is strictly best; ε=0.25 still explores 25% of the time on that state.
- `SKIP` Q is never updated from live closes (`update` uses `pos.direction` ∈ {BUY, SELL}), so SKIP stays 0.0 unless something else writes it (nothing else does).

---

## LEARNING / UPDATE BEHAVIOUR

```
Q[state][pos.direction] ← Q + 0.15 * (pnl - Q)
```

- State = entry `f"{round(trend,4)}_{round(vol,6)}"`.
- One global table for all six symbols.
- Learning is online and in-process only.
- A new `RLAgent()` (process start) has **zero** learned entries.

---

## PERSISTENCE ACROSS RESTARTS

None. No checkpoint, no DB column for Q, no load path. Restart ⇒ empty table ⇒ unseen-state 1/3 behaviour again.

---

## HISTORICAL OBSERVABILITY

| Wanted count | Can we measure it from existing live records? |
|---|---|
| Quant BUY signals | **No.** Stub votes are not stored. AI `allow=False` is a silent `return`. |
| Quant SELL signals | **No.** Same. |
| RL BUY / SELL / SKIP | **No** in retained Docker logs. Those events are `logger.info` (`[AI+RL]`, `RL decided to skip`, `RL gate blocked`). Retained logs (last 8000 lines) contain **0** of those strings. `alert()`/`print` lines such as `[OPEN]` **do** appear. |
| Quant/RL agreements | **No** (need both votes). |
| Quant/RL disagreements | **No.** |
| Trades vetoed solely by RL | **No** (those logs are missing from stdout). |
| Trades allowed by RL | **Not as RL.** A filled `[OPEN]` implies RL did **not** veto, but does not record `RL_Action`. |

**What the retained logs can measure (not RL/quant split):**  
Last 8000 Docker log lines: **84** `[OPEN]` lines — **45 BUY**, **39 SELL**. That is the **final executed side** after all gates, not the voter tuple.

Postgres `trades` / `exec_orders` store final side only; diagnostics are exit/MFE, not votes.

Do **not** treat 45/39 as RL frequencies. Do **not** invent historical RL decisions.

---

## Classification (Part 3)

Current RL behaviour is:

**stochastic + random fallback for unseen states**, and **partially learned** only for states that received an in-process close update in this process.

It is **not** deterministic.  
It is **not** a loaded trained model.  
How much of the **running** table is learned: **cannot determine** (Q size UNKNOWN).

This audit does **not** conclude whether that helps or hurts PnL.

---

## VERIFIED FINDINGS

1. Running container `ENSEMBLE_MODE=quant`, 1 local voter, 0 API voters; all LLM keys configured=false.
2. Workspace `.env` matches the container on those decision settings.
3. RL is always on; ε=0.25; α=0.15; no checkpoint; no `RL_*` env.
4. Unseen state Q is all zeros; action is uniform among BUY/SELL/SKIP.
5. Live RNG is unseeded stdlib `random`.
6. Identical state can yield different RL actions.
7. RL updates on successful close with raw PnL; table dies on restart.
8. `[AI+RL]` / skip / block logs are not in retained Docker stdout; `[OPEN]` is.
9. Focused tests: `tests/test_rl_unseen_state.py` + existing mapping tests — **13 passed**.

---

## UNKNOWN

- Number of keys in the **live** process `rl_agent.q`.
- How many of those keys have non-zero Q after ~2 days of this container.
- Historical RL BUY/SELL/SKIP counts (logs not on stdout; not in DB).
- Whether uvicorn file logs exist **inside** the container elsewhere — not searched beyond Docker stdout (would be extra; stdout already shows the gap).
- Worker model: compose runs `uvicorn forex_bot.a…` as a single container command; if multiple workers existed they would each have a separate empty-then-learned table. **LIKELY** one process from the compose command string; not independently proven.

---

## POTENTIAL PROBLEMS — NOT CHANGED

Facts only; no performance claim:

- For any unseen state, RL vetoes an AI BUY or SELL with probability **2/3**.
- ε=0.25 continues random actions even after a state has a unique best Q.
- SKIP is never trained online.
- Q is not persisted; every restart returns to empty-table randomness.
- RL decisions that matter (skip/block/action) are `logger.info` and are **absent** from retained Docker logs, so the live gate cannot be counted after the fact.
- Shared table / raw-price state across six pairs (from the prior audit) still applies.

---

## Tests and regression

Focused: `python -m pytest tests/test_rl_unseen_state.py tests/test_rl_action_mapping.py -q --tb=short` → **13 passed** in 0.06s.

Full normal suite: `python -m pytest -q --tb=line` → **299 passed, 1 failed** in 17.89s.

**Known separate failure (not disguised):**  
`tests/test_decision_quality_data.py::test_inventory_reports_missing_pairs` still expects five pairs to have no local CSV; the downloaded historical files exist (`74555 == 0`). Research-only. Historical CSVs were not modified. That test was not rewritten.

Production files changed: **none**.

**STOP.** No fix implemented. Await human review.
