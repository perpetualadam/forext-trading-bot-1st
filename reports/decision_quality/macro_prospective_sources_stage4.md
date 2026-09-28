# MACRO RESEARCH — PROSPECTIVE RECORDER STAGE 4
# AUTOMATIC FORECAST SOURCE DISCOVERY + APPROVED COLLECTION ADAPTERS

Research-only. No directional trading rule. No model. No production trading authority.
Stage 1–3 PIT safeguards are unchanged. `FORWARD_CONSENSUS_COLLECTION_ENABLED` remains false.
The Windows scheduled task was not modified. No genuine observation was written for
`usd_empsit_2026-10-02` (window opens 2026-09-30T12:30:00Z).

SOURCE AUDIT
------------
Classification is fail-closed. No source is APPROVED_AUTOMATION_READY.

| source_id | access method | auth | credentials | forecast fields | timestamps | individual | consensus | previous/revised | programmatic | local artifact | autonomous status | class | reason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| trading_economics | documented REST calendar (`Authorization` header; host `api.tradingeconomics.com`) | yes | NO | Forecast / ForecastValue / TEForecast (TE-owned, not Reuters) | Date UTC; LastUpdate = insertion/update, not proven pre-T0 vintage | NO | YES (TE calendar consensus) | YES | YES | UNKNOWN | disabled | API_AVAILABLE_CREDENTIALS_MISSING | API exists in-repo. Key absent. Archival/redistribution permission not established. |
| econoday | licensed XML feed (historical sample ZIP only) | yes | NO | CONSENSUS / range in licensed XML | RELEASED_ON_GMT when licensed | NO | YES | YES | NO (no live endpoint here) | UNKNOWN | disabled | MANUAL_ONLY | No live feed URL/credentials. HTML calendar is not an approved scrape target. |
| reuters | licensed newswire / paywalled pages | desk-dependent | NO | survey/range when printed | HIGH when original UTC clock present | YES | YES | sometimes | NO | UNKNOWN | disabled | MANUAL_ONLY | No Reuters API. Do not scrape paywalled pages. Manual ingest of lawfully obtained text remains allowed. |
| factset_insight | public insight posts / licensed FactSet | no for public posts | NO | labeled medians on some posts | date-only / Tomorrow; no UTC clock | NO | YES | NO | NO | UNKNOWN | disabled | MANUAL_ONLY | No automation permission. Live pages can be edited. |
| dow_jones | licensed Dow Jones / Newswires | yes | NO | survey consensus when licensed | HIGH when clocked relay exists | YES | YES | unknown | NO | UNKNOWN | disabled | MANUAL_ONLY | Primary feed not licensed here. Do not scrape paywalled DJ. |
| bloomberg | licensed terminal/API | yes | NO | survey/BN when licensed | HIGH when accessible | YES | YES | unknown | NO | UNKNOWN | disabled | MANUAL_ONLY | No Bloomberg credentials. Paywall. No bypass. |
| bls_official | official HTML news release | no | NO | n/a (actuals, not forecasts) | embargo clock | NO | NO | revisions exist; first print must stay immutable | PARTIAL (direct GET historically 403) | UNKNOWN for bulk scrape; public releases are citable | disabled | UNSUPPORTED | Official actuals only. Adapter implemented DISABLED. Never fetch before T0. |
| frb_official | federalreserve.gov statement HTML/PDF | no | NO | n/a (official decision) | For release at 2:00 p.m. | NO | NO | NO | YES | UNKNOWN | disabled | UNSUPPORTED | Official statement, not pre-release consensus. |
| fred_alfred | FRED/ALFRED vintage APIs | API key | NO | NO | vintage dates for official series | NO | NO | YES | YES | UNKNOWN | disabled | REJECTED | Official statistical vintages, not economist pre-release forecasts. |
| search_engine_snippets | Google/Bing/AI summaries | no | NO | unreliable snippets | NO | NO | NO | NO | NO | n/a | disabled | REJECTED | Not prospective evidence. |
| cme_fedwatch | contemporaneous citation of CME FedWatch | no | NO | implied probabilities when cited | citing article clock only | NO | NO | NO | NO | UNKNOWN | disabled | MANUAL_ONLY | Do not reconstruct history from today's live tool. |
| fxstreet | public analysis pages (historical FOMC citation) | no | NO | sometimes cites futures/survey | page byline when present | NO | NO | NO | NO | UNKNOWN | disabled | MANUAL_ONLY | No automation permission. Do not scrape. |
| fxmacrodata | documented REST predictions API | yes (plan) | NO | survey/compiled consensus when paid | unknown vintage clock | unknown | YES | unknown | YES | UNKNOWN | disabled | API_AVAILABLE_CREDENTIALS_MISSING | Prior coverage probe required a plan. No key. No new live request in Stage 4. |
| manual_operator | operator ingest | no | n/a | as supplied | OUR observed_at_utc | as supplied | as supplied | as supplied | NO | YES (operator-supplied bytes) | disabled | MANUAL_ONLY | Manual ingest allowed without enabling autonomous collection. |

Guest/demo Trading Economics credentials are not used. No account was registered. No paywall was bypassed.

EMPLOYMENT COVERAGE
-------------------
Target event: `usd_empsit_2026-10-02`, T0=`2026-10-02T12:30:00Z`, window open=`2026-09-30T12:30:00Z`.
Reference period on the event registry: `2026-09` (September 2026 labor-market data). Adapters store the source's own reference period; they do not infer it from the release month if the source disagrees.

Exact series mapping (fail closed; no substitutes):
- `nonfarm_payroll_change` (persons; `80k` → `80000` only when the unit is unambiguous)
- `unemployment_rate` (percent)
- `average_hourly_earnings_mom` (percent)
- `average_hourly_earnings_yoy` (percent)

ADP payrolls, jobless claims, private payrolls, participation rate, and JOLTS are rejected as NFP substitutes (`INVALID_SERIES`). Ambiguous units (`about 80-90k`) are rejected.

No APPROVED_AUTOMATION_READY source can collect these series autonomously. The schema and test-only TE adapter preserve all four series independently. Production TE collect remains a no-fetch stub until archival permission and credentials exist.

CPI COVERAGE
------------
Future event `usd_cpi_2026-10-14` is supported as four separate series:
- `headline_mom`
- `headline_yoy`
- `core_mom`
- `core_yoy`

They are not collapsed into one CPI forecast. Tests prove four independent observations.

FOMC COVERAGE
-------------
Future event `usd_fomc_statement_2026-10-28` stores a distribution (`hold`, `cut_25bp`, `cut_50bp`, `hike`) on `fomc_distribution`.
`refuse_fomc_collapse` blocks converting probabilities into a fake expected basis-point change.
This is schema/support only. No FOMC source is automation-ready.

PERMISSION / ACCESS STATUS
--------------------------
Fail closed unless ALL of the following are true before any network fetch:
1. `FORWARD_CONSENSUS_COLLECTION_ENABLED=true`
2. source.enabled=true
3. automated_collection_permitted=true
4. archival_permitted=true
5. automation_class=`APPROVED_AUTOMATION_READY`
6. required credential present (if the adapter declares one)

Unknown permission, missing credentials, disabled source, and unknown source make zero network requests.
Trading Economics is the only in-repo forecast REST API with a documented calendar schema, but:
- `TRADING_ECONOMICS_API_KEY` is not configured (name present: NO nonempty value)
- archival/redistribution permission is UNKNOWN
Therefore it cannot be APPROVED_AUTOMATION_READY even after a key is obtained, until archival permission is established in writing.

FX Macro Data has a documented predictions API; a prior coverage probe already showed forecast values require a paid plan. Stage 4 did not repeat that request.

ADAPTERS IMPLEMENTED
--------------------
Production (`build_production_adapters`; used by collect-due):
- `TradingEconomicsAdapter` — registered, gated, `collect()` returns `SOURCE_DISABLED` / `NOT_APPROVED` with **zero** HTTP.
- `OfficialBlsFirstPrintAdapter` — implemented, **disabled** (`OFFICIAL_BLS_FIRST_PRINT_ENABLED=false`, registry enabled=false). Never fetches before T0.
- `NeverFetchAdapter` — remaining registry sources. Never HTTP.

Test-only:
- `_ApprovedTeTestAdapter` — mock transport only. Not in `build_production_adapters`. Used to prove series mapping, provenance, failure modes, and PIT clocks without touching the real store.

LIVE PROBE RESULTS
------------------
Bounded capability probe: `live=False`.
Trading Economics: NO_PROBE_CREDENTIALS_MISSING (0 requests).
BLS official: NO_PROBE_DISABLED_FORECAST_SOURCE (0 requests).
FX Macro Data: no Stage 4 request (prior probe already established plan-gated access; archival unknown).
Reuters / FactSet / DJ / Bloomberg / Econoday: no programmatic access; no request.

TOTAL EXTERNAL REQUESTS THIS TASK: 0
Probe record: `data/research/macro/consensus_pit/prospective/probes/capability_probe.json`
Probes never write `observations/observations.jsonl`.

ARTIFACT RETENTION
------------------
Successful collection (test path only) writes content-addressed bytes under `artifacts/{sha256}.{ext}`.
SHA-256 is computed over the preserved bytes. Identical bytes reuse the existing file; different bytes create a new hash. Existing artifacts are never silently mutated.
Observation records keep `raw_artifact_hash`, `raw_artifact_sha256`, `raw_artifact_path` / `artifact_location`.
Autonomous collection is not enabled, so the real prospective artifact directory was not used for provider responses.

If a future source forbids full raw retention, Stage 4 still requires explicit written permission for the structured subset before enablement. Unknown retention → not approved.

PIT SAFETY
----------
- `observed_at_utc` is the recorder clock at collection. Never backdated. Operator/CLI cannot pass `observed_at_utc`.
- `source_publication_utc`, `source_updated_utc`, `observed_at_utc`, `retrieval_utc` are stored separately.
- Forecast ingest with `now >= T0` is `POST_T0_REJECTED` and writes no observation.
- Pre-window collect-due does not call adapters that would fetch; production adapters fetch nothing anyway.
- Multiple providers are stored independently. No house average.
- Multiple vintages are stored independently. Unchanged bytes reuse the artifact hash; the later checkpoint still records that we checked.
- Exact employment/CPI/FOMC series identity is preserved. Ambiguous units/series write nothing.
- Network / parse / 429 / auth failures write no observation.
- Real event registry for Employment / CPI / FOMC was not rewritten.
- Real observations remain empty.
- Historical GOLD/SILVER and official US PIT archive were not modified.

OFFICIAL BLS FIRST-PRINT ADAPTER
--------------------------------
Implemented: YES.
Enabled: NO.
Config: `OFFICIAL_BLS_FIRST_PRINT_ENABLED=false`.
Registry: `bls_official.enabled=false`, `automation_class=UNSUPPORTED`.
Behavior when later enabled: refuse all fetches with `now < T0`; parse fail-closed; first print is a separate `release_actuals` record; revisions are not first-print overwrites.
This is not a forecast source. Do not enable in this task.

TEST RESULTS
------------
`python -m pytest tests/test_macro_prospective_sources_stage4.py tests/test_macro_prospective_recorder_stage1.py tests/test_macro_prospective_recorder_stage2.py tests/test_macro_prospective_recorder_stage3.py tests/test_macro_consensus_pit_stage2.py -q`

64 passed.

Coverage vs required list:
1–4 unknown/disabled/permission-unclear/missing-credentials make no network request — PASS
5 credentials never appear in logs — PASS
6 successful adapter result preserves provenance — PASS (tmp mock TE)
7 observed_at uses actual retrieval time — PASS
8 observed_at cannot be backdated — PASS
9 post-T0 forecast rejected — PASS
10–12 exact NFP / unemployment / AHE MoM / AHE YoY — PASS
13 CPI four components remain separate — PASS
14 FOMC distribution remains distribution — PASS
15–17 multiple providers / disagreement / vintages — PASS
18 unchanged artifact hash reuse — PASS
19–20 ambiguous unit / series rejected — PASS
21 raw artifact hash verified — PASS
22–24 malformed / network / rate-limit write no observation — PASS
25–26 audit probe and pre-window response do not enter real dataset — PASS
27 tests use temporary directories — PASS
28–29 real event registry preserved; real observations unchanged — PASS
30 no trading imports/actions — PASS
31–34 Stage 1, Stage 2, Stage 3, consensus Stage 2 — PASS

PRODUCTION ISOLATION
--------------------
Adapters and scheduler do not import `forex_bot.bot_loop`, `forex_bot.oanda_exec`, `forex_bot.oanda_client`, production decision routing, risk sizing, RL, or V2 policy.
`forex_bot/bot_loop.py` does not import the prospective adapters.
Macro adapter failures cannot affect live trading: collect-due is a short-lived research CLI; network errors are recorded and skipped.
OANDA request count this task: 0.
Do not reuse OANDA's rate limiter. Macro requests are separate research infrastructure (none issued).

ACTIVATION PLAN
---------------
Do **not** set `FORWARD_CONSENSUS_COLLECTION_ENABLED=true` yet. No source qualifies.

Exact remaining requirements before any autonomous forecast collection:

1. Choose a source that can become APPROVED_AUTOMATION_READY. Today none qualify.
2. If Trading Economics is the candidate:
   a. Obtain a legitimate `TRADING_ECONOMICS_API_KEY` (operator-owned; do not invent/demo).
   b. Obtain written confirmation that automated retrieval **and** local research archival of calendar JSON are permitted under the subscribed terms.
   c. Implement the live `TradingEconomicsAdapter.collect()` path (currently a no-fetch stub; the mock adapter is tests-only).
   d. In `source_registry/sources.json` for `trading_economics` set:
      - `enabled`: true
      - `automated_collection_permitted`: true
      - `archival_permitted`: true
      - `automation_class`: `APPROVED_AUTOMATION_READY`
   e. Operator then sets `FORWARD_CONSENSUS_COLLECTION_ENABLED` to true in `data/research/macro/consensus_pit/prospective/config.json`.
3. Keep Reuters / FactSet / DJ / Bloomberg / Econoday MANUAL_ONLY until a licensed feed exists.
4. Keep official BLS first-print disabled until a separate operator review after T0 rules.
5. Do **not** edit the Windows task `ForexMacroProspectiveCollectDue`. It already runs `collect-due` every 5 minutes.
6. First live collect must still respect the Employment window: no genuine observation before `2026-09-30T12:30:00Z`.
7. If no source can meet archival + credential + programmatic requirements, obtain legitimate API/feed access rather than scraping.

NEXT SAFE STEP
--------------
Review this source/access audit. Activate only sources classified APPROVED_AUTOMATION_READY. If none qualify, obtain legitimate API/feed access rather than weakening PIT provenance or scraping restrictions.
STOP.
