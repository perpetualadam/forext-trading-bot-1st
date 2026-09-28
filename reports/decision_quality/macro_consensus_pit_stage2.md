# MACRO RESEARCH — CONSENSUS STAGE 2
# FULL HISTORICAL RECONSTRUCTION + FORWARD SNAPSHOT ARCHITECTURE

Research only. Two workstreams kept separate: historical reconstruction uses only evidence whose pre-release provenance can be demonstrated; forward snapshots use OUR observed_at_utc.
Official US PIT archive was not modified. Pilot evidence was not rewritten.

HISTORICAL EVENT UNIVERSE
-------------------------
total eligible: 29
pilot already researched: 9
remaining researched: 20
Remaining IDs frozen in data/research/macro/consensus_pit/historical/manifest/remaining_events.json BEFORE search. fx_outcomes_used=false.
Remaining: usd_cpi_2025-10-24, usd_cpi_2025-12-18, usd_cpi_2026-01-13, usd_cpi_2026-03-11, usd_cpi_2026-04-10, usd_cpi_2026-05-12, usd_cpi_2026-06-10, usd_empsit_2025-11-20, usd_empsit_2025-12-16, usd_empsit_2026-01-09, usd_empsit_2026-03-06, usd_empsit_2026-04-03, usd_empsit_2026-05-08, usd_empsit_2026-06-05, usd_empsit_2026-07-02, usd_fomc_statement_2025-10-29, usd_fomc_statement_2025-12-10, usd_fomc_statement_2026-03-18, usd_fomc_statement_2026-04-29, usd_fomc_statement_2026-06-17

HISTORICAL COVERAGE
-------------------
any expectation evidence: 29 / 29
PIT_SAFE: 7 / 29 events (usd_cpi_2025-10-24, usd_empsit_2026-08-07, usd_fomc_statement_2025-09-17, usd_fomc_statement_2025-10-29, usd_fomc_statement_2025-12-10, usd_fomc_statement_2026-01-28, usd_fomc_statement_2026-07-29)
PIT_SAFE_WITH_LIMITATION: 21 / 29 events
uncertain/rejected-only remaining events: 2 (usd_cpi_2025-12-18, usd_cpi_2026-01-13)

CPI COVERAGE
------------
events with evidence: 10
PIT_SAFE events: usd_cpi_2025-10-24
SILVER events: usd_cpi_2025-09-11, usd_cpi_2026-02-13, usd_cpi_2026-03-11, usd_cpi_2026-04-10, usd_cpi_2026-05-12, usd_cpi_2026-06-10, usd_cpi_2026-07-14
Series: FactSet typically headline/core YoY NSA median; Reuters often MoM+YoY headline/core. Nov 2025 (Dec 18) official first print includes 2-month SA; no matching 2m consensus was invented.

EMPLOYMENT COVERAGE
-------------------
events with evidence: 11
PIT_SAFE events: usd_empsit_2026-08-07
SILVER events: usd_empsit_2025-09-05, usd_empsit_2025-11-20, usd_empsit_2025-12-16, usd_empsit_2026-01-09, usd_empsit_2026-02-11, usd_empsit_2026-03-06, usd_empsit_2026-04-03, usd_empsit_2026-05-08, usd_empsit_2026-06-05, usd_empsit_2026-07-02, usd_empsit_2026-08-07
AHE generally missing on remaining FactSet Insight pages. Dec 2025 FactSet u-rate labeled November: REJECT_WRONG_SERIES.

FOMC COVERAGE
-------------
events with evidence: 8
PIT_SAFE events: usd_fomc_statement_2025-09-17, usd_fomc_statement_2025-10-29, usd_fomc_statement_2025-12-10, usd_fomc_statement_2026-01-28, usd_fomc_statement_2026-07-29
SILVER events: usd_fomc_statement_2026-03-18, usd_fomc_statement_2026-04-29, usd_fomc_statement_2026-06-17
Distributions stored. Survey vs futures-implied kept separate. No scalar-bp collapse. No FOMC FX backtest.

GOLD DATASET
------------
events: usd_cpi_2025-10-24, usd_empsit_2026-08-07, usd_fomc_statement_2025-09-17, usd_fomc_statement_2025-10-29, usd_fomc_statement_2025-12-10, usd_fomc_statement_2026-01-28, usd_fomc_statement_2026-07-29
series: usd_cpi_2025-10-24:headline_yoy; usd_empsit_2026-08-07:nonfarm_payroll_change; usd_empsit_2026-08-07:unemployment_rate; usd_fomc_statement_2025-09-17:expected_policy_decision; usd_fomc_statement_2025-10-29:expected_policy_decision; usd_fomc_statement_2025-12-10:expected_policy_decision; usd_fomc_statement_2025-12-10:market_implied_cut_probability; usd_fomc_statement_2026-01-28:expected_policy_decision; usd_fomc_statement_2026-01-28:market_implied_cut_probability; usd_fomc_statement_2026-07-29:expected_policy_decision; usd_fomc_statement_2026-07-29:market_implied_hike_probability
sources: CBS News, FXStreet, IBTimes UK, Reuters

SILVER DATASET
--------------
events: usd_cpi_2025-09-11, usd_cpi_2026-02-13, usd_cpi_2026-03-11, usd_cpi_2026-04-10, usd_cpi_2026-05-12, usd_cpi_2026-06-10, usd_cpi_2026-07-14, usd_empsit_2025-09-05, usd_empsit_2025-11-20, usd_empsit_2025-12-16, usd_empsit_2026-01-09, usd_empsit_2026-02-11, usd_empsit_2026-03-06, usd_empsit_2026-04-03, usd_empsit_2026-05-08, usd_empsit_2026-06-05, usd_empsit_2026-07-02, usd_empsit_2026-08-07, usd_fomc_statement_2026-03-18, usd_fomc_statement_2026-04-29, usd_fomc_statement_2026-06-17
series: usd_cpi_2025-09-11:core_mom; usd_cpi_2025-09-11:core_yoy; usd_cpi_2025-09-11:headline_mom; usd_cpi_2025-09-11:headline_yoy; usd_cpi_2026-02-13:core_mom; usd_cpi_2026-02-13:core_yoy; usd_cpi_2026-02-13:headline_mom; usd_cpi_2026-02-13:headline_yoy; usd_cpi_2026-03-11:core_yoy; usd_cpi_2026-03-11:headline_yoy; usd_cpi_2026-04-10:core_mom; usd_cpi_2026-04-10:core_yoy; usd_cpi_2026-04-10:headline_mom; usd_cpi_2026-04-10:headline_yoy; usd_cpi_2026-05-12:core_mom; usd_cpi_2026-05-12:core_yoy; usd_cpi_2026-05-12:headline_mom; usd_cpi_2026-05-12:headline_yoy; usd_cpi_2026-06-10:core_yoy; usd_cpi_2026-06-10:headline_yoy; usd_cpi_2026-07-14:core_mom; usd_cpi_2026-07-14:core_yoy; usd_cpi_2026-07-14:headline_mom; usd_cpi_2026-07-14:headline_yoy; usd_empsit_2025-09-05:average_hourly_earnings_mom; usd_empsit_2025-09-05:average_hourly_earnings_yoy; usd_empsit_2025-09-05:nonfarm_payroll_change; usd_empsit_2025-09-05:unemployment_rate; usd_empsit_2025-11-20:nonfarm_payroll_change; usd_empsit_2025-11-20:unemployment_rate; usd_empsit_2025-12-16:nonfarm_payroll_change; usd_empsit_2025-12-16:unemployment_rate; usd_empsit_2026-01-09:nonfarm_payroll_change; usd_empsit_2026-02-11:nonfarm_payroll_change; usd_empsit_2026-02-11:unemployment_rate; usd_empsit_2026-03-06:nonfarm_payroll_change; usd_empsit_2026-03-06:unemployment_rate; usd_empsit_2026-04-03:nonfarm_payroll_change; usd_empsit_2026-04-03:unemployment_rate; usd_empsit_2026-05-08:nonfarm_payroll_change; usd_empsit_2026-05-08:unemployment_rate; usd_empsit_2026-06-05:nonfarm_payroll_change; usd_empsit_2026-06-05:unemployment_rate; usd_empsit_2026-07-02:nonfarm_payroll_change; usd_empsit_2026-07-02:unemployment_rate; usd_empsit_2026-08-07:average_hourly_earnings_yoy; usd_empsit_2026-08-07:nonfarm_payroll_change; usd_empsit_2026-08-07:unemployment_rate; usd_fomc_statement_2026-03-18:expected_policy_decision; usd_fomc_statement_2026-04-29:expected_policy_decision; usd_fomc_statement_2026-06-17:expected_policy_decision
limitations: Reuters same-morning Updated without last-mod; FactSet date-only + Tomorrow; delayed-release early vintages; uncounted FOMC color; path-level polls not meeting-specific.
SILVER is not invalid. It is excluded from the strict surprise dataset.

SOURCE/VINTAGE FINDINGS
-----------------------
- Publication-time proof and content-vintage proof remain separate. Archiving a page today does not prove the visible forecast existed before historical T0.
- Reuters poll articles whose untimed Updated marker falls on a calendar day strictly before T0 can be PIT_SAFE (Oct 21/22 vs Oct 24 CPI and Oct 29 FOMC; Dec 4 vs Dec 10 FOMC).
- Reuters BLS same-morning previews remain PIT_SAFE_WITH_LIMITATION when Updated is the T0 calendar day.
- T0-day Reuters without a UTC clock stays UNCERTAIN (Nov 20 employment; Jun 10 CPI).
- FactSet Insight remains SILVER: date + Tomorrow, no clock. Independently evaluated; URL pattern is not auto-approval.
- Instant View / actuals wraps quoting 'economists had forecast' are REJECT_POST_RELEASE.
- No lawful Wayback content-vintage upgrade was obtained in this session.
- Bloomberg paywall not opened. No illicit mirrors.

MULTI-SOURCE DISAGREEMENT
-------------------------
- usd_cpi_2026-02-13 headline_yoy: FactSet Insight=2.4; Reuters=2.5
- usd_cpi_2026-04-10 headline_yoy: FactSet Insight=3.4; Reuters=3.3
- usd_cpi_2026-07-14 core_yoy: FactSet Insight=2.9; Reuters=2.8
- usd_empsit_2025-09-05 nonfarm_payroll_change: FactSet Insight=80000; Reuters=75000
- usd_empsit_2025-09-05 unemployment_rate: FactSet Insight=4.2; Reuters=4.3
- usd_empsit_2026-02-11 nonfarm_payroll_change: FactSet Insight=75000; Reuters=70000
- usd_empsit_2026-08-07 nonfarm_payroll_change: FactSet Insight=97500; IBTimes UK=83000; Reuters=80000
- usd_fomc_statement_2026-06-17 expected_policy_decision: Reuters=hold; Reuters=cut_25bp
Providers were not averaged. No house consensus.

CONSENSUS EVOLUTION AVAILABLE
-----------------------------
- usd_empsit_2025-11-20: FactSet Oct 2 (T0-49d) vs Reuters Nov 20 unclocked same-day preview (not overwritten).
- usd_fomc_statement_2026-06-17: Mar 12 Reuters 63/96 June-cut vintage vs Jun 17 10:03Z uncounted hold preview. Both stored.
- usd_fomc_statement_2026-03-18 vs 2026-04-29 vs 2026-06-17: successive Reuters polls show hold-then-later-cut then hold-at-June; vintages kept separate.
Not analyzed against FX.

STRICT RAW SURPRISE COVERAGE
----------------------------
CPI: 1 records / 1 events
Employment: 2 records / 1 events
FOMC: 5 records / 5 events (expected_change_bp mapping only; probabilities have no surprise_raw)
total: 8 surprise-capable GOLD records
- usd_fomc_statement_2025-09-17 expected_policy_decision forecast=cut_25bp actual=-25 surprise_raw=0.0
- usd_fomc_statement_2026-01-28 expected_policy_decision forecast=hold actual=0 surprise_raw=0.0
- usd_empsit_2026-08-07 nonfarm_payroll_change forecast=83000 actual=-23000 surprise_raw=-106000.0
- usd_empsit_2026-08-07 unemployment_rate forecast=4.2 actual=4.1 surprise_raw=-0.10000000000000053
- usd_fomc_statement_2026-07-29 expected_policy_decision forecast=hold actual=0 surprise_raw=0.0
- usd_cpi_2025-10-24 headline_yoy forecast=3.1 actual=3.0 surprise_raw=-0.10000000000000009
- usd_fomc_statement_2025-10-29 expected_policy_decision forecast=cut_25bp actual=-25 surprise_raw=0.0
- usd_fomc_statement_2025-12-10 expected_policy_decision forecast=cut_25bp actual=-25 surprise_raw=0.0

FORWARD SNAPSHOT ARCHITECTURE
-----------------------------
Research-only store under data/research/macro/consensus_pit/forward/.
Schema includes snapshot_id, observed_at_utc (OUR clock), source_publication_utc (separate), SHA-256 of observed bytes, snapshot_sequence, pit_status.
final_pre_release_snapshot := latest snapshot with observed_at_utc < official_release_utc. Post-T0 observations cannot become final consensus.
Designed cadence (not a trading rule): T0-48h, T0-24h, T0-12h, T0-4h, T0-1h.
Compatible with later join to us_pit first prints. No FX surprise model run.

IMMUTABILITY VALIDATION
-----------------------
Append-only JSONL. Identical bytes/hash reuse snapshot_id and log a new observation. Changed bytes create a new snapshot_id, hash, sequence, observed_at.
Tests cover append, dedupe, new vintage, observed_at preservation, separate source clocks, post-T0 exclusion from final consensus, SHA-256 linkage.

SOURCE REGISTRY
---------------
data/research/macro/consensus_pit/forward/source_registry.json
Reuters, FactSet Insight, Dow Jones/IBTimes relay, CME FedWatch citation, Bloomberg. enabled=false on every source. archival/automation permitted=unknown unless proven.

COLLECTION ENABLED:
NO
FORWARD_CONSENSUS_COLLECTION_ENABLED=false. No collector, scheduler, Docker, or production bot integration.

CAN HISTORICAL CONSENSUS MINING SCALE?
PARTIAL
Documentary pre-release numbers exist for most remaining events, but GOLD still requires both a pre-T0 clock AND content-vintage proof. Same-day Reuters Updated and FactSet date-only keep the bulk of CPI/Employment in SILVER.

IS GOLD DATASET LARGE ENOUGH FOR FX SURPRISE RESEARCH?
NO
Additional coverage required: PIT_SAFE scalar CPI and Employment vintages with proven pre-T0 forecast text (WARC/last-mod, provider-preserved original, or our own future observed_at_utc) across the remaining SILVER-only CPI/NFP events; exact-series matches for irregular prints (Nov 2025 2-month SA); AHE where official values exist; meeting-specific FOMC distributions rather than path-level polls. Do not promote SILVER to GOLD to enlarge n.

CAN SILVER DATA BE USED AS SENSITIVITY ANALYSIS LATER?
YES
Reason: SILVER records have documentary pre-release semantics and often a pre-T0 clock; the limitation is unproven intra-day/content vintage, not a missing forecast. They must remain a separate sensitivity set, never mixed into the strict GOLD surprise file.

FORWARD PIT ARCHITECTURE READY:
YES
Schemas, hashing, immutable append, source registry, disabled collection, and tests are in place. Live collection is not enabled.

SURPRISE FX BACKTEST RUN:
NO
MODEL TRAINED:
NO
PRODUCTION CHANGE:
NO
V2 POLICY CHANGE:
NO
OANDA/API REQUESTS:
0
OFFICIAL US PIT ARCHIVE MODIFIED:
NO
FORWARD COLLECTION ENABLED:
NO
FILES CHANGED:
- data/research/macro/consensus_pit/historical/ (raw, evidence, manifest, normalized, gold, silver)
- data/research/macro/consensus_pit/forward/ (config, schema, registry)
- reports/decision_quality/_macro_consensus_pit_stage2.py
- reports/decision_quality/_macro_consensus_forward.py
- reports/decision_quality/macro_consensus_pit_stage2.md
- tests/test_macro_consensus_pit_stage2.py
STOP.
