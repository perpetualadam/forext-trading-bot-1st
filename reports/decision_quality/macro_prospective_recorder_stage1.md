# MACRO RESEARCH — PROSPECTIVE RECORDER STAGE 1
# 48-HOUR PRE-RELEASE CONSENSUS + ECONOMIC CALENDAR + FIRST-PRINT RECORDER

Research-only data collection infrastructure. No directional trading rule. No model. No production trading authority.
Existing historical GOLD/SILVER evidence was not rewritten. Official US PIT archive was not modified.

ARCHITECTURE
------------
Prospective store: `data/research/macro/consensus_pit/prospective/`.
Core helper: `reports/decision_quality/_macro_prospective_recorder.py`.
Separate clocks: source_publication_utc, source_updated_utc, observed_at_utc (OUR clock), official_release_utc.
Pre-release requires observed_at_utc < T0. T0 is not a pre-release checkpoint.
Observations reference immutable SHA-256 artifact bytes. Identical bytes are reused; changed bytes create a new artifact.
Official first prints live in `release_actuals/` and cannot overwrite pre-T0 observations.
Future FX linkage schema preserves six USD pairs and USD_SIGN; +1m is not fabricated from M5. No directional analysis in this stage.

EVENT REGISTRY
--------------
Families: CPI, EMPLOYMENT_SITUATION, FOMC.
Required fields include macro_event_id, official schedule, 48h window start/end, event_status.
T0 is taken from an official schedule (UTC or local+timezone). Historical averages are not used to invent a clock.
America/New_York DST is applied when converting official local wall times to UTC.

48-HOUR WINDOW
--------------
observation_window_start_utc = T0 - 48 hours (timezone-aware UTC).
observation_window_end_utc = T0.
Window math is 48 UTC hours, not 48 local hours, so DST transitions do not silently shift PIT order.

CHECKPOINTS
-----------
Frozen before outcomes: T0-48h, T0-36h, T0-24h, T0-12h, T0-6h, T0-4h, T0-2h, T0-1h, T0-30m, T0-15m, T0-5m.
T0 is RELEASE/POST-RELEASE. Not optimized on FX results.

SOURCE REGISTRY
---------------
`source_registry/sources.json`. enabled=false by default. Unknown permissions fail closed.
Reuters, FactSet, Dow Jones, Bloomberg, Trading Economics are registered and disabled.
Autonomous collection requires FORWARD_CONSENSUS_COLLECTION_ENABLED=true AND source.enabled=true AND automated_collection_permitted=true.
Manual ingest may use a registered source without enabling autonomous collection.

ECONOMIC CALENDAR STORAGE
-------------------------
observation_kind=ECONOMIC_CALENDAR. expectation_type=ECONOMIC_CALENDAR_FORECAST.
Calendar forecast/previous/revised_previous/importance remain provider-specific. Not relabeled as Reuters/FactSet/DJ consensus.

FORECASTER STORAGE
------------------
SURVEY_CONSENSUS, SURVEY_MEDIAN, SURVEY_MEAN, PROVIDER_CONSENSUS, INDIVIDUAL_FORECAST, MARKET_IMPLIED_EXPECTATION stored separately.
INDIVIDUAL_FORECAST is never consensus. Providers are never averaged.
CPI series: headline/core MoM/YoY with SA/NSA. Employment: NFP, u-rate, AHE MoM/YoY. FOMC distributions are not collapsed to scalar bp.

IMMUTABLE ARTIFACT STORAGE
--------------------------
Content-addressed files `artifacts/{sha256}.{ext}`. SHA-256 over actual preserved bytes. Parsed values reference the hash.

OBSERVATION VS ARTIFACT
-----------------------
Each checkpoint writes an observation timestamp. Unchanged bytes reuse the artifact hash. Changed bytes create a new hash and a new observation.

OFFICIAL FIRST-PRINT STORAGE
----------------------------
`release_actuals/actuals.jsonl` with record_kind=FIRST_PRINT. Revisions are separate REVISION records. First print cannot be overwritten.

RELEASE-TIME RACE PROTECTION
----------------------------
observed_at_utc compared to T0. Post-T0 pages are OBSERVED_POST_T0 and cannot become final_pre_release_observation.
Pre-T0 artifact hashes remain on disk. Calendar actual-overwrite after T0 is a new observation, not an edit.

RESTART / IDEMPOTENCY
---------------------
Recorder reconstructs events, observations, artifacts, first-print status, and identity index from disk.
Identical re-ingest: ALREADY_EXISTS. Same logical identity with incompatible payload: CONFLICT (fail closed).
State machine: SCHEDULED -> PRE_WINDOW -> COLLECTING_PRE_RELEASE -> FINAL_PRE_RELEASE_CAPTURED -> RELEASE_PENDING -> FIRST_PRINT_CAPTURED -> POST_RELEASE_OBSERVATION -> COMPLETE, plus explicit failure states.

DRY-RUN RESULT
--------------
Fixture event fixture_empsit_2026-10-02, T0=2026-10-02T12:30:00Z, window_start=2026-09-30T12:30:00Z.
Provider A 175k (48h/24h) then 165k (6h) then 160k (1h/5m). Unchanged 5m reuses hash.
Provider B 170k -> 165k. Provider C individual 160k from T0-6h, not relabeled consensus.
Final pre-T0 Provider A: checkpoint=T0-5m value=160000 observed_at=2026-10-02T12:25:00Z
Post-T0 calendar update did not alter final pre-T0 record: True
First official actual stored separately: 110000. Derived surprise vs Provider A final 160k is infrastructure-only: {'value_quality': 'PRESENT', 'surprise_raw': -50000.0, 'actual': 110000, 'final_pre_release': 160000, 'source_id': 'fixture_provider_a', 'observed_at_utc': '2026-10-02T12:25:00Z', 'notes': 'derived field only. no FX research.'}
n_observations=19 n_artifacts=13 collection_enabled=False
Numbers are not an economic interpretation.

TEST RESULT
-----------
26 passed (12 prospective recorder + 14 consensus stage2)

SECURITY / ACCESS LIMITS
------------------------
No paywall/CAPTCHA/auth/robots bypass. Unknown sources fail closed. Autonomous collection disabled.
Recorder does not import bot_loop, oanda_exec, oanda_client, execution, or v2_shadow.
bot_loop does not import the recorder. Zero OANDA requests. No Docker deploy. No production logic change.

PROSPECTIVE RECORDER STAGE 1
----------------------------
48H WINDOW IMPLEMENTED: YES
CHECKPOINTS IMPLEMENTED: YES
CHECKPOINTS: T0-48h, T0-36h, T0-24h, T0-12h, T0-6h, T0-4h, T0-2h, T0-1h, T0-30m, T0-15m, T0-5m
EVENT REGISTRY READY: YES
CPI SCHEMA READY: YES
EMPLOYMENT SCHEMA READY: YES
FOMC SCHEMA READY: YES
ECONOMIC CALENDAR SNAPSHOTS READY: YES
MULTI-FORECASTER SNAPSHOTS READY: YES
MANUAL INGEST READY: YES
OBSERVED_AT_UTC PRESERVED: YES
SOURCE_PUBLICATION_UTC KEPT SEPARATE: YES
IMMUTABLE ARTIFACTS: YES
SHA-256: YES
FINAL PRE-T0 SNAPSHOT PROTECTED: YES
FIRST OFFICIAL ACTUAL STORED SEPARATELY: YES
REVISIONS CANNOT OVERWRITE FIRST PRINT: YES
RESTART SAFE: YES
IDEMPOTENT: YES
UNKNOWN SOURCES FAIL CLOSED: YES
AUTONOMOUS EXTERNAL COLLECTION ENABLED: NO
GLOBAL COLLECTION FLAG: FORWARD_CONSENSUS_COLLECTION_ENABLED=false
PRODUCTION TRADING AUTHORITY: NONE
OANDA/API REQUESTS: 0
PRODUCTION LOGIC MODIFIED: NO
V2 POLICY MODIFIED: NO
MODEL TRAINED: NO
DIRECTIONAL RULE CREATED: NO
SURPRISE FX BACKTEST RUN: NO
TESTS: 26 passed (12 prospective recorder + 14 consensus stage2)
FILES CHANGED:
- data/research/macro/consensus_pit/prospective/
- reports/decision_quality/_macro_prospective_recorder.py
- reports/decision_quality/macro_prospective_recorder_stage1.md
- tests/test_macro_prospective_recorder_stage1.py
NEXT SAFE STEP: Register the next officially scheduled US CPI, Employment Situation, or FOMC T0 from the BLS/Fed calendar; lawfully capture manual pre-release artifacts inside the 48h window with observed_at_utc; leave autonomous source enablement false until a specific source has documented archival/automation permission.
STOP.
