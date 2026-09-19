# Quant V2 — information / data acquisition and evaluation plan

**Status:** PLAN ONLY. Nothing was trained, downloaded, or deployed.

**Parent freeze:** `reports/decision_quality/quant_v1_final_assessment.md`  
**V1 verdict:** NO ECONOMICALLY USEFUL EVENT FOUND on 2025-09 through 2026-08 M5 mid technicals.

Quant V2 is **not** “more indicators on the same mid OHLC.” It is a plan for **new causal information**, **honest evaluation**, and **gates before any ML training**.

Progress file: `reports/decision_quality/quant_v2_research_plan_progress.json`.

---

## Stage 3 — Current raw-data inventory

Inspected locally. Nothing was downloaded.

### Historical market files

| Path | What it is |
| --- | --- |
| `data/historical/{EUR,GBP,USD_JPY,AUD,USD_CAD,USD_CHF}_USD_M5.csv` | Approved six-pair research cache, 2025-09-01 00:00 – 2026-08-31 23:50 UTC |
| `data/research/quant_features/six_pair_features.pkl` | Derived mid-feature cache (447,027 rows). Not a new raw source |
| `data/eurusd_m5_2024_sample.csv` | Short **synthetic** mid-only sample for backtest format. Not research-grade |
| `data/README.txt` | Documents mid `time,open,high,low,close`; says optional volume is for generic CSV backtests |

Canonical historical columns (from files + `history_cache.CSV_COLUMNS`):

| Field | Present on six M5 CSVs | Used in Quant V1 research | Classification |
| --- | --- | --- | --- |
| M5 mid OHLC | **Yes** | **Yes** (primary) | AVAILABLE HISTORICALLY |
| M5 bid OHLC | **Yes** (`bid_open/high/low/close`) | **No** (explicitly unused) | AVAILABLE HISTORICALLY |
| M5 ask OHLC | **Yes** | **No** | AVAILABLE HISTORICALLY |
| volume | **Yes** (integer-like, e.g. 231, 435) | **No**. `csv_ohlcv` ignores it | AVAILABLE HISTORICALLY |
| spread from bid/ask | **Derivable** (not a stored column) | **No** (modeled half-spread used instead) | AVAILABLE HISTORICALLY |
| timestamp | **Yes** (bar start UTC) | Yes | AVAILABLE HISTORICALLY |
| complete flag | **Yes** (all `True` in cache) | Completed-only policy | AVAILABLE HISTORICALLY |

### Other raw categories

| Source | Classification | Evidence |
| --- | --- | --- |
| M1 candles | **NOT PRESENT** on disk | No `*_M1.csv`. Live/research clients *can* request other granularities (see Stage 4) |
| S5 candles | **NOT PRESENT** | Not in cache; not in local granularity map |
| Tick / pricing-stream captures | **NOT PRESENT** | No stream module, no tick files |
| Order-book / depth | **NOT PRESENT** | No code, no files |
| Economic calendar / news | **NOT PRESENT** | No calendar tables or files |
| Interest-rate / yield / macro series | **NOT PRESENT** | No rate files |
| Other timeframe raw files (M15/H1/H4) | **NOT PRESENT** as raw | V1 **derived** closed HTF from M5 mid only |
| Broker fills / account trades | **AVAILABLE LIVE ONLY** (and local DB when the bot writes) | `forex_bot/database.py` `trades` / `exec_orders`; research note `live_trades_note.txt` = live-trade read failed. Not a six-pair market history |
| Operational / reconcile logs | **AVAILABLE LIVE ONLY** | Process logs, not a research panel |
| Pricing snapshots (rest) | **NOT PRESENT** historically | Live path uses mid candles, not stored snapshots |

**Implication:** the only unused **historical** market fields already on disk are **bid/ask OHLC** and **volume**. Everything else is missing or live-only.

---

## Stage 4 — OANDA read-only capability (local code/docs only)

No requests were made. Classification is “what this repo already knows how to call,” not a live capability probe.

| Data type | Repo support | Classification |
| --- | --- | --- |
| Mid candles | `oanda_client.fetch_ohlcv` / `fetch_ohlcv_range` (`price=M`); research `oanda_candles_read` (`price=MBA`) | HISTORICALLY AVAILABLE via existing read-only candle GET. **M5 MBA already downloaded** |
| Bid/ask candles | Research downloader `HISTORY_PRICE = "MBA"`; already stored on the six CSVs | HISTORICALLY AVAILABLE (cached). Live `fetch_ohlcv` does **not** request bid/ask |
| Volume on candles | Parsed from InstrumentsCandles `volume` into the cache | HISTORICALLY AVAILABLE as that field. Semantics: Stage 6 |
| Other granularities | `oanda_client._GRANULARITY_MINUTES` lists **M1, M5, M15, M30, H1, H4, D**. Research downloader **hard-codes M5** | HISTORICALLY AVAILABLE **in principle** through the same InstrumentsCandles client; **not implemented** as a research cache for non-M5. Depth of history: **UNKNOWN / REQUIRES EXTERNAL VERIFICATION** |
| S5 / S10 | **Not** in the local granularity map | UNKNOWN / REQUIRES EXTERNAL VERIFICATION |
| Spread | Not a separate endpoint. Derivable from MBA candles or live bid/ask | HISTORICALLY AVAILABLE from cached bid/ask; live mid path does not persist it |
| Instrument metadata | Local `symbols.py` / pip size. No Instruments instrument-definition GET | UNKNOWN as an API dump; **local constants exist** |
| Account summary (NAV) | `fetch_account_summary` | LIVE / account-state. Not a market feature |
| Open positions / pending orders / trade details | `oanda_exec` + reconciliation | LIVE / account-state. Do not use for Quant V2 market labels |
| Transaction / account history dump | No Transactions endpoint import | UNKNOWN / not implemented. Account-specific even if added |
| Live pricing stream | **Not implemented** | LIVE-CAPTURE ONLY if built later. No historical stream archive |
| Historical order book / depth | **Not implemented**; do not assume OANDA stores it | NOT AVAILABLE in-repo. Historical depth: **UNKNOWN / do not assume it exists** |

Safety: research candle GET is isolated (`oanda_candles_read` must never place/cancel orders). Any future download stays in a **separate CLI process**, dry-run unless `--confirm`, and must not share assumptions with the live limiter.

**Do not download in this task.**

---

## Stage 5 — Microstructure plan (existing bid/ask candles)

V1 used mid + a **constant modeled** half-spread. The CSVs already contain per-bar bid and ask OHLC. That is new information **without** another mid indicator.

### Candidate features (not tested)

| Candidate | New vs mid OHLC? | Causal at bar close? | Coverage | Plausible role |
| --- | --- | --- | --- | --- |
| Close spread `(ask_close − bid_close)` | **Yes** | Yes | Six CSVs, full year | **TRADEABILITY/COST**; maybe MAGNITUDE if spread marks stress |
| Spread change / return | Yes | Yes | same | COST / regime |
| Spread percentile vs TRAIN-only past | Yes | Yes if rolling uses t and earlier only | same | COST / opportunity filter |
| Spread expansion/contraction event (enter TRAIN extreme) | Yes | Yes | same | MAGNITUDE or **do-not-trade**; weak direction expected |
| Bid range vs ask range asymmetry | Yes (side-specific OHLC) | Yes | same | Uncertain; could be noise or quote-stuffing artifact |
| Bid vs ask realized range / volatility difference | Yes | Yes | same | Uncertain |
| Spread around **already-defined** session transitions | Yes | Yes | same | COST / tradeability at London open, not a new clock hunt |
| Spread around vol-expand events (V1 definition) | Yes | Yes | same | COST conditional on V1 vol event |

**Do not** compute mid RSI on bid close and call it microstructure.

**Expected primary use:** decide when a 1-pip modeled cost is a lie (spread already 2–4 pips) and when two-sided M5 noise is **not** tradeable. That addresses V1 Stage 6 (almost every bar “clears” 1× **modeled** cost).

**Direction:** possible but not assumed. Pass only if gates in Stage 16 hold.

**Leakage:** use completed-bar bid/ask only; do not use the next bar’s spread to label the current decision.

---

## Stage 6 — Volume information plan

### What the field is, from this repository

- Stored as OANDA InstrumentsCandles `volume` (`oanda_candles_read.parse_candles_payload`).
- Persisted on the six M5 CSVs.
- Production `csv_ohlcv.load_ohlcv_csv` **ignores** volume.
- Quant V1 feature/event studies **did not** use it.
- Local docs **do not** define the unit. `data/README.txt` only says optional volume exists on generic CSVs.

**Do not assume this is centralized FX volume.** FX is OTC; a broker candle `volume` is typically **activity on that broker’s price updates**, not global turnover. Exact OANDA definition: **UNKNOWN / REQUIRES EXTERNAL VERIFICATION** before any economic story is attached. Until then treat it as **relative activity on this feed**.

### Possible research uses (not run)

| Use | Construction (causal) | Likely role |
| --- | --- | --- |
| Relative activity | volume / rolling median of past N bars, TRAIN quantiles | MAGNITUDE / opportunity / execution context |
| Volume surprise | current vs same-session historical distribution (existing session buckets only) | MAGNITUDE / context |
| Volume expansion event | enter TRAIN upper quantile (transition, not every high-vol bar) | MAGNITUDE; maybe TRADEABILITY |
| Volume × range | high volume + small range vs high volume + large range | MAGNITUDE / rejection context |
| Session-relative activity | volume vs that session’s past | context; **not** a new session search |

**Direction:** not the default hypothesis (V1 vol *level* failed; vol *transition* was two-sided).  
**Do not test until Experiment A.**

---

## Stage 7 — Cross-currency structure plan (do not repeat V1)

V1 already tested: other-pairs median USD-direction `ret_6`, agreement count, TRAIN-extreme `usd_own − median`, and one combo with range-bottom. Those are on the do-not-rediscover register (V1-12, V1-13, V1-14).

New hypotheses must be **predeclared**, small in number, and mathematically different.

### USD orientation (unchanged, causal)

Positive USD-direction return:

- EUR_USD, GBP_USD, AUD_USD: `−r`
- USD_JPY, USD_CAD, USD_CHF: `+r`

Use **other pairs only** for factor construction when the target is one of the six. Align on completed timestamps; no interpolation.

| ID | Hypothesis | Definition | Alignment | Target | Why new vs V1 | Mining risk | Expected frequency |
| --- | --- | --- | --- | --- | --- | --- | --- |
| X1 | Common USD factor | First cross-sectional mean/median of the **five others’** USD-returns at t (V1 used this as *context*). **New part:** use it only as a **regressor to residualize**, not as a standalone event | Same t, completed | Residual, not raw mid | V1 tested the factor’s level/extreme. V2 tests the **idiosyncratic leftover** | Medium if many residual windows | Every synchronized bar |
| X2 | Pair residual | `usd_own(t) − β̂_train * usd_others(t)` with **TRAIN-only** β, or simply `own − others_med` **already used** — **do not reuse the simple subtract as a new event**. Allowed new form: residual after TRAIN β, then **enter** residual q1/q5 | Same t | 60–240m residual close and path | β-adjusted residual ≠ raw divergence tail | Medium | Transition events, not every bar |
| X3 | Cross-sectional dispersion | Std or IQR of the five others’ USD-returns at t | Same t | Future **absolute** movement / two-sided MFE | V1 did not test dispersion as a **magnitude** event | Low if one predeclared measure | High-dispersion transitions |
| X4 | Lead/lag | Other-pairs USD factor at t vs target return at t+h only as **label**; feature = factor at t. Optional: factor change from t−k to t with **one** predeclared k (e.g. 6 bars) | Factor at t; no future pairs | Direction of target after factor move | V1 was contemporaneous agreement, not a fixed lag test | High if k is searched | Factor-move events |
| X5 | Synchronized vs idiosyncratic | Event: \|own residual\| small **and** \|factor\| large (sync) vs \|residual\| large and \|factor\| small (idio) | Same t | Path after sync vs idio | Different partition than V1 extreme divergence | Medium | Two predeclared states only |
| X6 | Relative-value dislocation | Spread of two **quote** pairs (e.g. EUR_USD − GBP_USD) vs TRAIN residual of that spread — **one** pair-spread, predeclared, not a 15-pair search | Same t | Mean-reversion of that spread, then map back to legs | V1 used a USD basket, not a named basis | High if several bases are tried | Extreme-entry events |

**Controls:** TRAIN-only edges; event transitions; event-level n; no combinatorial pairing of X1–X6 with V1 events except at most **two** predeclared combos written down before results.

**Do not run these in this task.**

---

## Stage 8 — Lower-timeframe data plan

V1 fact: at 1× cost, **~22.5%** of 15–480m path-orders are **AMBIGUOUS** because both thresholds can print in the same M5 bar. MFE-up and MFE-down are also large and two-sided. M5 aggregation **hides order**.

| Source | What it would add | Availability (local knowledge) | Storage (order of magnitude, 6 pairs × 1 year) | API | History vs future |
| --- | --- | --- | --- | --- | --- |
| M1 candles (MBA) | Intrabar path order at 1-minute resolution; tighter MFE timing; rejection/breakout sequence; more realistic same-bar SL/TP | Repo can request M1; **not cached**. Historical depth UNKNOWN without a probe | ~5× M5 ≈ **2.2M** rows; MBA width similar to current CSVs (tens of MB, not TB) | Same InstrumentsCandles; more pages; must stay off the live process | Likely **historical** if OANDA serves M1 for the year — verify later, do not assume full coverage |
| S5 | Finer path and spread path | Not in local granularity map | ~60× M5 ≈ **27M** rows | More pages / limiter risk | UNKNOWN |
| Tick / pricing stream | True tradeable bid/ask path; execution realism | Not implemented | Unbounded; needs rotation | New stream client | **LIVE-CAPTURE ONLY** going forward. Cannot reconstruct V1 year |

**Research uses if M1 is later authorized:**

- Path-order labels that are currently AMBIGUOUS on M5
- Breakout: did price fail immediately (first 1–3 minutes) or continue
- Impulse: continuation vs immediate giveback
- Spread path inside the M5 bar (if MBA M1 exists)
- Execution sim: stop-before-target with known minute order (V1 already refuses same-bar TP when order is unknown)

**Do not download or capture in this task.**

---

## Stage 9 — Macro / calendar plan

**Inventory:** the repository has **no** historical economic-calendar, news, or macro-release tables. Session code uses timezone calendars (BST/GMT), not economic events. `backtest.py` has **hand-curated regime date windows** for stress/calm years — those are not a release calendar and must not be treated as timestamped surprises.

### Future causal schema (vendor not selected)

| Field | When it may be used |
| --- | --- |
| event_type (CPI, NFP, FOMC, GDP, PMI, …) | Known **before** release if the schedule was published |
| scheduled_ts_utc | Known before |
| currencies_affected | Known before |
| minutes_to_event | Known before; **stop using after** the release prints |
| consensus / forecast | Only if a **historical vintage** exists with `asof ≤ scheduled_ts` |
| released_value | Only at/after `released_ts` (may differ from scheduled) |
| surprise | Only after release, and only if consensus was causally available |
| revised_value | Only after revision timestamp |

### Leakage (severe)

- Using “the print” on bars **before** `released_ts`
- Using revised prints as if they were first prints
- Using consensus scraped today as if it existed last year
- Building events from **future** realized volatility around a time-of-day (that is outcome leakage)
- Searching many event types × windows × pairs after seeing results

**Goal is not** to predict the release. Possible targets: post-release path, pre-release no-trade, or magnitude around scheduled times using **only pre-release fields**.

Do not pick a vendor in this task. Do not fetch a calendar.

---

## Stage 10 — Rate / carry plan

**Inventory:** no policy-rate, OIS, or yield files in the repo.

| Concept | Speed | Plausible use | Not a use |
| --- | --- | --- | --- |
| Policy rate / target rate | Days to months | **Regime / pair selection / longer-horizon bias** | M5 entry timing |
| Short-rate differential (e.g. 2y or 3m) | Slow | Carry / regime; who is the high-yielder | Bar-by-bar BUY/SELL |
| Change in differential | Event-like when a decision prints | Post-decision response (needs calendar + rates) | Searching daily changes as fake M5 signals |

Distinguish **slow context** (valid as a feature that is constant across hundreds of M5 bars — independence collapses) from **M5 timing**. Carry is more appropriate for **H1+ horizons, pair selection, and regime**, not another every-bar classifier.

Do not obtain data in this task.

---

## Stage 11 — Quant V2 target options

Do not pick one from theory alone. None is authorized for training until Stage 16 gates pass.

### 1. Direction conditional on a genuine event

- **Data:** new info (spread/volume/residual/macro), not V1 mid-only events unless they are **controls**
- **Label:** sign of future mid (or bid/ask-aware) move **only on event rows**
- **Horizon:** predeclare 30/60/120m; do not pick the best
- **Cost:** event must change the distribution of **unique** favorable path vs 1× **realized or modeled** cost
- **Independence:** event n, not persistent state
- **Leakage:** event definition frozen before VALIDATION
- **Min evidence:** Stage 16 gates 1–5

### 2. Magnitude / volatility opportunity

- **Data:** spread, volume surprise, dispersion (X3), vol-expand as **control only**
- **Label:** future abs excursion or realized range vs cost multiples; **not** UP/DOWN
- **Horizon:** 60/240m predeclared
- **Cost:** useful if it predicts when 2×/3× moves occur **or** when spread makes 1× unreachable
- **Independence:** transitions
- **Leakage:** do not use future realized vol in the feature
- **Min evidence:** stable magnitude lift that changes a tradeability decision, not +0.2 pip

### 3. Path-order target using lower-timeframe data

- **Data:** M1 (or finer) after authorized download
- **Label:** UP_FIRST / DOWN_FIRST / NEITHER with **much lower** AMBIGUOUS rate
- **Horizon:** 15–60m path
- **Cost:** threshold = 1× and 2× **bar-close spread** if MBA exists
- **Independence:** events or non-overlapping blocks
- **Leakage:** M1 after decision time is **label-only**
- **Min evidence:** AMBIGUOUS rate drops materially; remaining tilt clears cost gates

### 4. Relative-value / cross-pair target

- **Data:** six M5 (already); residual/basis from Stage 7
- **Label:** residual or named-spread future change
- **Horizon:** 60–240m
- **Cost:** must clear **sum of** relevant half-spreads (two legs if a spread trade — even if the bot only trades one leg, be honest)
- **Independence:** residual-extreme **entries**
- **Leakage:** self-inclusion; using target return inside the factor
- **Min evidence:** differs from V1-12/13; multi-pair or predeclared single basis holds OOS

### 5. Post-macro-event response

- **Data:** calendar + post-release prints with vintage timestamps; M5 or M1 path
- **Label:** signed or absolute move **after** `released_ts`
- **Horizon:** 15–240m after release
- **Cost:** news spreads often **widen** — use contemporaneous bid/ask, not 1.0 pip fiction
- **Independence:** one row per event × currency
- **Leakage:** see Stage 9 (severe)
- **Min evidence:** gates + vendor vintage audit; n large enough after filtering

### 6. Longer-horizon directional target

- **Data:** rates/carry and/or residual factors; H1/H4 closes
- **Label:** sign of 4h–5d move
- **Horizon:** H4 / D, not every M5
- **Cost:** fewer trades; spread is a smaller fraction of move **if** the move exists — not automatic
- **Independence:** non-overlapping holds or weekly blocks
- **Leakage:** overlapping 5-day labels on every M5
- **Min evidence:** walk-forward on development + later holdout; no M5-style n inflation

---

## Stage 12 — Timeframe question

V1 effects on **M5 labels** are small versus spread. That does **not** prove H1 is better.

| Timeframe | Cost-to-move | Sample | Holding / overlap | Spread relevance |
| --- | --- | --- | --- | --- |
| M5 | V1: typical 60m close effects 0.1–0.8 pips vs 1–1.5 pip cost. Two-sided MFE already > cost | ~75k bars/pair/year | High overlap if every bar is a sample | Dominant |
| M15 | Larger typical range; still many overlapping labels | ~1/3 of M5 | Better if one decision per closed M15 | Still large unless events are rare |
| H1 | Move more often exceeds 1 pip; direction may still be 50% | ~6k bars/pair/year | Need non-overlapping or daily blocks | Less dominant **if** there is a real bias |
| H4 | Sparse; regime/carry more natural | ~1.5k / pair / year | Independence easier; power worse | Cost often small vs range; **edge still required** |

**Do not assume slower is better.** A 51% H1 hit with 4-hour two-sided noise can still lose after spread and stop geometry (V1 SL/TP already showed ~27% wins at 2R).

Future comparison (not run now): same **predeclared** information set, labels at M5/M15/H1/H4, **event-level or non-overlapping** samples, same cost hurdle in pips **and** in ATR.

---

## Stage 13 — Future data policy

### Formal status of the inspected year

**2025-09-01 00:00 UTC through 2026-08-31 23:50 UTC = DEVELOPMENT / DISCOVERY.**

Allowed later: feature engineering, hypothesis generation, training, walk-forward **inside development**, method debugging.

**Forbidden:** calling any split of this year a pristine final holdout; “OOS proof” in a model card; retuning V1 hypotheses and announcing discovery.

Once any **new** holdout is inspected, **it becomes development history** and a still-later holdout is required.

### Proposed policy (do not download now)

| Bucket | Period | Use |
| --- | --- | --- |
| DEV0 | 2025-09-01 – 2026-08-31 | Frozen discovery archive. Never overwrite `data/historical/*_M5.csv` |
| DEV-WF | Walk-forward **inside DEV0** and/or later appended development | Model selection only. Report as development |
| HOLDOUT1 | Genuinely **later** completed M5 (from 2026-09-01 UTC onward) in a **separate directory** e.g. `data/historical/holdout_YYYYMM/` | Unopened until gates 1–5 pass on development |
| HOLDOUT2 | Still later, after HOLDOUT1 is burned | Next acceptance |

**When HOLDOUT1 may be opened:** written freeze of features, events, and a single predeclared target; development walk-forward complete; no further threshold edits.

**Failure on HOLDOUT1:** effect missing, below cost, or unstable across symbols. Outcome: **do not train for production**. Archive as development. Design the next test on **new** information or wait for HOLDOUT2.

**After inspection:** label HOLDOUT1 as “inspected development.” Do not reopen for tuning and then cite it again as final.

Acquisition of later M5: existing **read-only** downloader, separate process, `--confirm` only when authorized, never into the live bot, never overwriting DEV0.

---

## Stage 14 — Data-acquisition priorities

Ranked by **new information × causal availability × historical availability × low complexity × leakage control × ability to falsify V2 cheaply**. Not a trading recommendation.

| Rank | Category | New info | Causal | Historical now | Complexity | Leakage | Expected research value | Rationale |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Existing bid/ask + spread** | High vs V1 mid-only | Yes | **Already on disk** | Lowest | Low if completed-bar | High for **cost/tradeability**; unknown for direction | V1’s 1× hurdle used a **constant** spread while 70% of bars look “two-sided tradeable.” Real spread is the cheapest untested field |
| 2 | **Existing volume** | Medium (activity; not FX volume) | Yes | **Already on disk** | Lowest | Low | Medium for magnitude/context | Same files as #1; unused; semantics must stay humble |
| 3 | **Richer cross-pair structure** | Medium if residual/dispersion/lag, **not** V1 median USD | Yes | Same six M5 | Low | Medium (alignment, mining) | Medium; **easy to falsify** | Simple USD already failed; residuals/dispersion are the only leftover structure in-house |
| 4 | **Lower-timeframe candles (M1 first)** | High for path-order | Yes if downloaded | API in-repo; **not on disk** | Medium (authorized download, pages, disk) | Medium (label vs feature time) | High for **path-order / execution**; unknown for edge | Directly addresses 22.5% AMBIGUOUS. Do not start until #1–#3 are specified and A/B have run or been scheduled |
| 5 | **Economic calendar + vintage releases** | High around events | Only with vintage timestamps | **Not present** | High (vendor, join, leakage audit) | **Severe** | High if done cleanly; otherwise worthless | Can create moves much larger than spread; not available locally; not next |
| 6 | **Rates / yields** | Medium, slow | Yes if timestamped | **Not present** | Medium | Medium (revisions) | Better for regime / longer horizon than M5 | Mismatched to V1 M5 timing failure |
| 7 | **Future pricing-stream capture** | High for execution | Live only | **None** | High | Low if stored with exchange time | Future-only; cannot study DEV0 | Build later for HOLDOUT execution realism, not for rediscovering 2025-09–2026-08 |
| — | Account fills / Postgres trades | Execution diagnostics | Live | Sparse / read failed in research | — | — | Not a market-information panel | Out of Quant V2 information rank |
| — | More mid technicals on DEV0 | **None** | Yes | Yes | Low | High (reuse) | **Negative** (wastes time) | Explicitly deprioritized |

---

## Stage 15 — Next experiments (designed, not run)

Prefer cheap falsification. Sequence follows Stage 14.

### Experiment A — Bid/ask, spread, and volume (existing CSVs)

- **HYPOTHESIS:** Completed-bar spread and relative volume contain information about **tradeability/cost** and possibly **magnitude**. Direction is **not** assumed.
- **NEW INFORMATION:** bid/ask OHLC, derived spread, volume-as-activity.
- **TARGET:** (i) next-60m two-sided MFE vs **this bar’s** close spread; (ii) signed 60m close (secondary); (iii) path-order with threshold = 1× **realized** close spread.
- **DATA:** existing six M5 MBA CSVs. No download.
- **FIXED CONTROLS:** TRAIN-only quantiles; event = **enter** extreme spread or volume state; V1 range-bottom / breakout as **controls only**, not retuned; same splits as V1 with DISCOVERY_TEST labeled inspected.
- **VALIDATION:** chronological train/valid/discovery_test + six symbols + event bootstrap seed 42.
- **COST HURDLE:** unique favorable close or unique path must exceed **that bar’s** half-spread, not 1.0 pip fiction. GBP still wider in model if realized spread missing.
- **PASS:** Gate 1–4 on **tradeability or magnitude** (e.g. high-spread state predicts that 1× modeled cost is not enough; or volume-expand predicts abs move with CI excluding the complement). Direction pass only if also Gate 3.
- **FAIL:** spread/volume do not change future-path distributions beyond noise, or only reproduce V1 two-sidedness.
- **COMPUTE:** vectorized, O(N), same class as the event study (minutes, not hours).

### Experiment B — Residual / dispersion cross-pair (not V1 USD)

- **HYPOTHESIS:** After removing a TRAIN-fit common USD factor, **idiosyncratic** extremes or **dispersion transitions** change future residual or abs-move distributions.
- **NEW INFORMATION:** X2 residual (TRAIN β) and X3 dispersion only. **Do not** retest V1-12/13 events.
- **TARGET:** residual 60m close; abs excursion for dispersion.
- **DATA:** same six M5 mids.
- **FIXED CONTROLS:** other-pairs-only factor; predeclared one β method; transition events; max **two** combinations written before run.
- **VALIDATION:** same chronological + symbol rules.
- **COST HURDLE:** 1× half-spread on the **target pair**; if a spread-trade story is told, sum of legs.
- **PASS:** residual or dispersion effect stable and ≥ cost gate.  
- **FAIL:** same size as V1 USD (~0–0.15 pips) or symbol-unstable.
- **COMPUTE:** panel join + vectorized; minutes.

### Experiment C — M1 path-order (only after authorization)

- **HYPOTHESIS:** A material fraction of V1 AMBIGUOUS 1×-cost orders resolve on M1, and some predeclared events then show a **unique** path that clears realized spread.
- **NEW INFORMATION:** M1 MBA path inside/after the M5 decision bar (**labels**).
- **TARGET:** path-order UP_FIRST / DOWN_FIRST / NEITHER; AMBIGUOUS rate vs M5.
- **DATA:** new dated M1 cache; **do not overwrite** M5 DEV0. Not authorized in this task.
- **FIXED CONTROLS:** reuse **frozen** V1 event definitions as controls; do not retune lookbacks.
- **VALIDATION:** same year is still development; M1 does not create a new holdout.
- **COST HURDLE:** 1× and 2× M1-close or M5-close spread.
- **PASS:** AMBIGUOUS rate drops enough to measure path-order; remaining tilt meets Gate 3.  
- **FAIL:** order resolves to ~50/50 or still below cost.
- **COMPUTE:** larger I/O; still linear in bars; not the old trade loop.

### Experiment D — Macro-event (later)

- Only after a vintage calendar exists. Predeclare event types (FOMC, CPI, NFP, BOE, RBA, …). Features before release; labels after `released_ts`. Fail if n or leakage audit fails.

### Experiment E — Longer horizon (later)

- Only if A–C fail for M5 direction **or** rates data arrives. H1/H4 non-overlapping labels. Fail if overlap is used to inflate n.

**Chosen sequence:** **A → B → (C if authorized) → D/E only with new files.**  
Do not run A–E now.

---

## Stage 16 — Go / no-go gates (before any ML training)

A future Cursor run **cannot** declare success from a +0.2 pip effect below spread.

| Gate | Requirement | Fail if |
| --- | --- | --- |
| **G1 Information** | Predeclared feature/event changes the **distribution** of the predeclared target vs a predeclared complement/control. Report event n, not bar n. | Effect is a persistent-state recount of V1; or only in-sample |
| **G2 Chronology** | Same **sign** (or same magnitude direction) in TRAIN and VALIDATION. DISCOVERY_TEST on DEV0 is **descriptive only**. Later HOLDOUT1 required for acceptance | VALIDATION flips; or DEV0 test is sold as final OOS |
| **G3 Economic** | Typical **unique** favorable quantity ≥ **1.0× contemporaneous entry half-spread** (realized close spread if available, else modeled). “Unique” means adverse MFE is not essentially equal and path-order is not ~symmetric / ~22% ambiguous without LTF resolution. Block/event bootstrap 5–95% interval must lie **entirely above** the 1× hurdle for the **signed economic metric** (e.g. mean close, or P(UP_FIRST)−P(DOWN_FIRST) translated to pips) | Mean close +0.2–0.8 pips vs ~1 pip cost; MFE-up ≈ MFE-down; CI includes values below 1× |
| **G4 Sample** | Event n ≥ 300 in VALIDATION **and** ≥ 50 per symbol if a BROAD claim is made. INSUFFICIENT otherwise | n=30 compression-exit style claims |
| **G5 Causal live path** | Every feature is computable from information the bot could have at the **completed** decision bar (or at `released_ts` for post-macro). No future candles, no revised prints, no self-included factor | Cannot implement without lookahead |
| **G6 Train** | **Then and only then** may a model be trained on DEV0, selected by walk-forward on DEV0, and **accepted only on a later unopened holdout** | Training to “confirm” a below-cost V1 pattern |

**BROAD vs PAIR-SPECIFIC:** a BROAD claim needs G2+G3 on at least 5/6 symbols. One strong pair is PAIR-SPECIFIC and cannot be aggregated to hide losers.

**MAGNITUDE-ONLY models** still need G3 in **cost units** (e.g. predicted move vs spread) and must not be described as directional.

---

## Stage 17 — Quant V2 roadmap

Do not jump from a statistical blip to live trading.

| Stage | Name | Allowed now? | Exit criterion |
| --- | --- | --- | --- |
| 0 | **V1 freeze** | Done (this pair of reports) | Register V1-01–V1-18 |
| 1 | **DATA ACQUISITION** | Plan only. First **authorized** action is Experiment A/B on **existing** CSVs (no download). Later: dated M1/holdout dirs | Files validated; DEV0 never overwritten |
| 2 | **INFORMATION STUDY** | A then B, then maybe C | G1–G4 written; fail closed |
| 3 | **TARGET DESIGN** | After a study **passes** G1–G5 | Single frozen target spec |
| 4 | **MODEL TRAINING** | Only after G6 | Walk-forward on development; no production stub change |
| 5 | **TRADING SIMULATION** | After a model exists | Costs = realized or modeled spread; SL/TP explicit; no silent mid fills |
| 6 | **SHADOW / PAPER VALIDATION** | After sim | Paper ≠ broker; no OrderCreate. Compare to frozen baseline |
| 7 | **LIVE DEPLOYMENT REVIEW** | Human only | Separate go-live review. Changing `_quant_stub_vote` is **not** implied by any V2 study |

**Hard stops already in force:**

- Do not search this dataset for another mid technical rule.
- Do not train on V1 targets.
- Do not implement event filters in production from V1.
- Do not download, stream, or call external APIs until a later explicit authorization.
- Do not restart Docker or the live bot for this plan.

---

## What this task did not do

No download, no training, no production/quant/RL/SL/TP/session/risk/execution changes, no broker writes, no historical CSV modification.

Wait for human review before Experiment A.
