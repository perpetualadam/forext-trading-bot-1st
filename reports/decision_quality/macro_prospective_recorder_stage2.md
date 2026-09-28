# MACRO RESEARCH — PROSPECTIVE RECORDER STAGE 2
# FIRST REAL EVENT REGISTRATION + 48H ARMING

Research-only. No directional trading rule. No model. No production trading authority.
Historical GOLD/SILVER evidence was not rewritten. Official US PIT archive `data/research/macro/us_pit/` was not modified.
Stage 1 fixture `fixture_empsit_2026-10-02` remains infrastructure-only under `fixtures/dry_run/` and is not a registered real event.

OFFICIAL SOURCES USED
---------------------
T0 authority is BLS/Federal Reserve, not an economic-calendar provider.

- BLS CPI release calendar: https://www.bls.gov/schedule/news_release/cpi.htm
  Retrieved during Stage 2 execution. Table: September 2026 | Oct. 14, 2026 | 08:30 AM.
  Timezone: America/New_York (BLS national news-release convention). DST-aware ZoneInfo conversion; EDT/EST was not hardcoded.
- BLS Employment Situation release calendar: https://www.bls.gov/schedule/news_release/empsit.htm
  Retrieved during Stage 2 execution. Table: September 2026 | Oct. 02, 2026 | 08:30 AM.
  Timezone: America/New_York. DST-aware ZoneInfo conversion.
- Federal Reserve FOMC calendar: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
  2026 meetings: October 27-28 (next after September 15-16, which already has a published statement).
- Federal Reserve statement release clock: official FOMC statement header "For release at 2:00 p.m."
  Example: https://www.federalreserve.gov/monetarypolicy/files/monetary20260916a1.pdf (16 Sep 2026).
  Applied as 14:00 America/New_York on the statement day (28 Oct 2026). DST-aware conversion.

Provenance excerpts and SHA-256 hashes live in:
`data/research/macro/consensus_pit/prospective/manifests/official_schedule_provenance.json`
and `.../official_schedule_excerpts/`.

The coincidental overlap between the Stage 1 fixture name `fixture_empsit_2026-10-02` and the real BLS Employment Situation date is not treated as proof. Real registration used the BLS table, a distinct event id `usd_empsit_2026-10-02`, and official provenance URLs.

REGISTERED EVENTS
-----------------
All three families were registered because official schedules were available and T0 is after execution UTC.

macro_event_id: usd_empsit_2026-10-02
family: EMPLOYMENT_SITUATION
official T0 local: 2026-10-02T08:30:00 America/New_York
official T0 UTC: 2026-10-02T12:30:00Z
window start UTC: 2026-09-30T12:30:00Z
source/provenance: https://www.bls.gov/schedule/news_release/empsit.htm (September 2026 / Oct. 02, 2026 / 08:30 AM)

macro_event_id: usd_cpi_2026-10-14
family: CPI
official T0 local: 2026-10-14T08:30:00 America/New_York
official T0 UTC: 2026-10-14T12:30:00Z
window start UTC: 2026-10-12T12:30:00Z
source/provenance: https://www.bls.gov/schedule/news_release/cpi.htm (September 2026 / Oct. 14, 2026 / 08:30 AM)

macro_event_id: usd_fomc_statement_2026-10-28
family: FOMC
official T0 local: 2026-10-28T14:00:00 America/New_York
official T0 UTC: 2026-10-28T18:00:00Z
window start UTC: 2026-10-26T18:00:00Z
source/provenance: FOMC calendar October 27-28; statement clock 2:00 p.m. ET from Fed statement release line.

NEXT EVENT
----------
usd_empsit_2026-10-02 (earliest T0 among registered future events; not selected by FX importance).

REAL CHECKPOINT SCHEDULE
------------------------
Frozen Stage 1 offsets. T0 is not a pre-release checkpoint. Employment (NEXT EVENT):

T0-48h  2026-09-30T12:30:00Z
T0-36h  2026-10-01T00:30:00Z
T0-24h  2026-10-01T12:30:00Z
T0-12h  2026-10-02T00:30:00Z
T0-6h   2026-10-02T06:30:00Z
T0-4h   2026-10-02T08:30:00Z
T0-2h   2026-10-02T10:30:00Z
T0-1h   2026-10-02T11:30:00Z
T0-30m  2026-10-02T12:00:00Z
T0-15m  2026-10-02T12:15:00Z
T0-5m   2026-10-02T12:25:00Z

CPI and FOMC checkpoint UTC maps are in `events/events.json` and `manifests/armed_checkpoints.json`.

Association rule (deterministic): latest_checkpoint_at_or_before_observed_at_utc.
Interval is [checkpoint_utc, next_checkpoint_utc); last interval is [T0-5m, T0).
The observation keeps its genuine observed_at_utc. The timestamp is never rewritten to the checkpoint clock.
CAPTURED if any qualifying pre-release observation associates to that checkpoint.
DUE if now >= checkpoint_utc and now < next_boundary and not CAPTURED.
MISSED_NOT_OBSERVED if now >= next_boundary and not CAPTURED.
FUTURE if now < checkpoint_utc.
Missed is not a zero forecast. No observations were manufactured for passed checkpoints (none had passed at registration).

CURRENT STATE
-------------
CURRENT UTC at registration/status: 2026-09-28T21:35:10Z / 2026-09-28T21:35:23Z
NEXT EVENT state: PRE_WINDOW
All 11 checkpoints: FUTURE
Next checkpoint: T0-48h at 2026-09-30T12:30:00Z
Real observations recorded: 0
CPI and FOMC also PRE_WINDOW.

MANUAL INGEST WORKFLOW
----------------------
Operator command (do not backdate; recorder stamps observed_at_utc):

python -m reports.decision_quality.macro_prospective_cli ingest --event <macro_event_id> --source-id <source_id> --expectation-type <type> --series <series> --forecast-value <value> --unit <unit> --reference-period <period> --artifact <path> [--source-publication-utc ...] [--notes ...]

Literal copied text is allowed with `--text` and is stored as the artifact with retrieval_method=manual.
`--kind ECONOMIC_CALENDAR` stores provider/event name/scheduled time/importance/forecast/previous/revised previous without merging into Reuters/FactSet/etc.
`--observed-at-utc` is refused (OPERATOR_BACKDATE_FORBIDDEN). Tests inject a clock; the production CLI cannot supply observed_at_utc.
SHA-256 is required. Identical bytes reuse the artifact. A changed forecast is a new vintage. Same logical identity with a different payload fails closed (CONFLICT).
Autonomous Reuters/FactSet/Dow Jones/Bloomberg/Trading Economics collection remains disabled. Manual lawful evidence from those publishers may still be recorded.

STATUS WORKFLOW
---------------
python -m reports.decision_quality.macro_prospective_cli status
python -m reports.decision_quality.macro_prospective_cli due

Local disk only. Zero external requests. No OS scheduler, cron, Docker cron, or daemon was created.

PERSISTENCE AUDIT
-----------------
Prospective store: `data/research/macro/consensus_pit/prospective/` (host workspace).
`docker-compose.yml` bind-mounts only `./data/research/v2_shadow:/app/data/research/v2_shadow`.
The prospective tree is not bind-mounted. Container recreate would not persist this directory unless some other unstated volume exists.
Host-side operator CLI writes persist in the workspace tree.
Docker deployment was not modified.

ACCESS / SOURCE LIMITATIONS
---------------------------
No paywall/CAPTCHA/auth/robots bypass. Unknown sources fail closed.
FORWARD_CONSENSUS_COLLECTION_ENABLED=false.
FOMC calendar page lists meeting dates, not a clock; 14:00 ET is taken from the Fed's published statement release line.
BLS schedule tables print 08:30 AM without spelling "ET" on the fetched table; timezone is the BLS national news-release convention already used in this project's official PIT archive, converted with ZoneInfo.
Economic-calendar forecasts remain provider-specific.

TEST RESULTS
------------
python -m pytest tests/test_macro_prospective_recorder_stage1.py tests/test_macro_prospective_recorder_stage2.py tests/test_macro_consensus_pit_stage2.py -q
38 passed (Stage 1 prospective + Stage 2 prospective + Stage 2 consensus).
Covered: official registration, next-event selection, T0-48h, 11 checkpoints, NY DST, PRE_WINDOW, COLLECTING_PRE_RELEASE, FUTURE/DUE/MISSED_NOT_OBSERVED, CLI backdate refusal, operator clock, pre-T0 / ==T0 / >T0, artifact hash reuse, new vintage, restart, idempotent ingest, conflict fail-closed, autonomous disabled, status/due local-only, no fake observations in the real registry, no production trading import path, first-print path in tmp only.

PRODUCTION SAFETY
-----------------
No production signal, quant stub, RL, V2 policy, SL/TP, ATR, profit protection, sizing, portfolio, OANDA, live execution, or strategy routing changes.
No training. No FX surprise research. No directional rule.
bot_loop does not import the recorder or CLI.

PROSPECTIVE RECORDER STAGE 2
----------------------------
OFFICIAL SCHEDULE VERIFIED: YES
REGISTERED CPI: usd_cpi_2026-10-14
CPI T0 UTC: 2026-10-14T12:30:00Z
REGISTERED EMPLOYMENT: usd_empsit_2026-10-02
EMPLOYMENT T0 UTC: 2026-10-02T12:30:00Z
REGISTERED FOMC: usd_fomc_statement_2026-10-28
FOMC T0 UTC: 2026-10-28T18:00:00Z
NEXT EVENT: usd_empsit_2026-10-02
48H WINDOW OPENS: 2026-09-30T12:30:00Z
CURRENT STATE: PRE_WINDOW
CHECKPOINTS ARMED: YES
REAL OBSERVATIONS RECORDED: 0
FAKE/FIXTURE OBSERVATIONS IN REAL DATA: 0
MANUAL INGEST CLI READY: YES
STATUS CLI READY: YES
DUE CLI READY: YES
OPERATOR CAN BACKDATE observed_at_utc: NO
ARTIFACT HASH REQUIRED: YES
FINAL PRE-T0 PROTECTION: YES
FIRST-PRINT PATH READY: YES
AUTONOMOUS EXTERNAL COLLECTION: OFF
FORWARD_CONSENSUS_COLLECTION_ENABLED: false
PROSPECTIVE DIRECTORY PERSISTENT: NO
EXTERNAL REQUESTS FROM STATUS/DUE: 0
PRODUCTION TRADING AUTHORITY: NONE
OANDA/API REQUESTS: 0
PRODUCTION LOGIC MODIFIED: NO
V2 POLICY MODIFIED: NO
MODEL TRAINED: NO
DIRECTIONAL RULE CREATED: NO
FX SURPRISE BACKTEST RUN: NO
NEXT SAFE STEP: When the Employment Situation 48-hour window opens at 2026-09-30T12:30:00Z, lawfully capture a genuine pre-release forecast/calendar excerpt and ingest it with the CLI. Leave autonomous collection false. Do not create schedulers yet.
STOP.
