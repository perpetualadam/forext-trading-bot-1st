# MACRO RESEARCH — CONSENSUS STAGE 1
# HISTORICAL PRE-RELEASE CONSENSUS MINING PILOT

Research only. Not price-derived consensus. Not today's calendar forecast field.
Official actuals joined from `data/research/macro/us_pit/` (read, not modified).
No FX-performance analysis. No model. No production change.

PILOT SELECTION
---------------
Frozen in `data/research/macro/consensus_pit/pilot/SELECTION.md` BEFORE any consensus search.
Rule: from the 29 Stage-3 eligible PIT-approved events, within each family pick earliest T0, T0 closest to the midpoint of that family's first/last T0 (tie-break earlier), and latest T0. Calendar geometry only. FX outcomes were not used.
CPI: usd_cpi_2025-09-11, usd_cpi_2026-02-13, usd_cpi_2026-07-14
Employment: usd_empsit_2025-09-05, usd_empsit_2026-02-11, usd_empsit_2026-08-07
FOMC: usd_fomc_statement_2025-09-17, usd_fomc_statement_2026-01-28, usd_fomc_statement_2026-07-29

CPI RESULTS
-----------
- usd_cpi_2025-09-11 | SURVEY_MEDIAN | headline_yoy=2.9 percent | FactSet | pub=2025-09-10 | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2025-09-11 | SURVEY_MEDIAN | core_yoy=3.1 percent | FactSet | pub=2025-09-10 | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2025-09-11 | PROVIDER_CONSENSUS | headline_mom=0.3 percent | FactSet via Morningstar | pub=2025-09-09 | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2025-09-11 | INDIVIDUAL_FORECAST | core_mom=0.36 percent | Goldman Sachs | pub=2025-09-09 | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-02-13 | SURVEY_CONSENSUS | headline_mom=0.3 percent | Reuters | pub=2026-02-13T05:04:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-02-13 | SURVEY_CONSENSUS | headline_yoy=2.5 percent | Reuters | pub=2026-02-13T05:04:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-02-13 | SURVEY_CONSENSUS | core_mom=0.3 percent | Reuters | pub=2026-02-13T05:04:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-02-13 | SURVEY_CONSENSUS | core_yoy=2.5 percent | Reuters | pub=2026-02-13T05:04:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-02-13 | SURVEY_MEDIAN | headline_yoy=2.4 percent | FactSet | pub=2026-02-12 | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-07-14 | SURVEY_CONSENSUS | headline_yoy=3.8 percent | Reuters | pub=2026-07-14T04:02:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-07-14 | SURVEY_CONSENSUS | headline_mom=-0.1 percent | Reuters | pub=2026-07-14T04:02:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-07-14 | SURVEY_CONSENSUS | core_yoy=2.8 percent | Reuters | pub=2026-07-14T04:02:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-07-14 | SURVEY_CONSENSUS | core_mom=0.2 percent | Reuters | pub=2026-07-14T04:02:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-07-14 | SURVEY_MEDIAN | headline_yoy=3.8 percent | FactSet | pub=2026-07-13 | PIT=PIT_SAFE_WITH_LIMITATION
- usd_cpi_2026-07-14 | SURVEY_MEDIAN | core_yoy=2.9 percent | FactSet | pub=2026-07-13 | PIT=PIT_SAFE_WITH_LIMITATION
A/B/C/D/E/F/G by event: all 3 CPI events have pre-release artifacts and exact series semantics for at least headline YoY; UTC clocks exist on Reuters same-morning previews (PIT_SAFE_WITH_LIMITATION due to same-day Updated). No CPI record was promoted to PIT_SAFE because FactSet pages lack clocks and Reuters BLS previews carry an untimed same-day Updated line. Joinable official first prints exist for standard MoM/YoY series. Strict PIT_SAFE surprise: none for CPI.

EMPLOYMENT RESULTS
------------------
- usd_empsit_2025-09-05 | SURVEY_CONSENSUS | nonfarm_payroll_change=75000 persons | Reuters | pub=2025-09-05T04:09:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2025-09-05 | SURVEY_CONSENSUS | unemployment_rate=4.3 percent | Reuters | pub=2025-09-05T04:09:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2025-09-05 | SURVEY_CONSENSUS | average_hourly_earnings_mom=0.3 percent | Reuters | pub=2025-09-05T04:09:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2025-09-05 | SURVEY_CONSENSUS | average_hourly_earnings_yoy=3.7 percent | Reuters | pub=2025-09-05T04:09:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2025-09-05 | SURVEY_MEDIAN | nonfarm_payroll_change=80000 persons | FactSet | pub=2025-09-04 | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2025-09-05 | SURVEY_MEDIAN | unemployment_rate=4.2 percent | FactSet | pub=2025-09-04 | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2026-02-11 | SURVEY_CONSENSUS | nonfarm_payroll_change=70000 persons | Reuters | pub=2026-02-11T05:03:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2026-02-11 | SURVEY_CONSENSUS | unemployment_rate=4.4 percent | Reuters | pub=2026-02-11T05:03:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2026-02-11 | SURVEY_MEDIAN | nonfarm_payroll_change=75000 persons | FactSet | pub=2026-02-10 | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2026-08-07 | SURVEY_CONSENSUS | nonfarm_payroll_change=80000 persons | Reuters | pub=2026-08-07T04:02:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2026-08-07 | SURVEY_CONSENSUS | unemployment_rate=4.2 percent | Reuters | pub=2026-08-07T04:02:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2026-08-07 | SURVEY_CONSENSUS | average_hourly_earnings_yoy=3.5 percent | Reuters | pub=2026-08-07T04:02:00Z | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2026-08-07 | SURVEY_MEDIAN | nonfarm_payroll_change=97500 persons | FactSet | pub=2026-08-06 | PIT=PIT_SAFE_WITH_LIMITATION
- usd_empsit_2026-08-07 | SURVEY_CONSENSUS | nonfarm_payroll_change=83000 persons | Dow Jones | pub=2026-08-07T07:51:00Z | PIT=PIT_SAFE
- usd_empsit_2026-08-07 | SURVEY_CONSENSUS | unemployment_rate=4.2 percent | Dow Jones | pub=2026-08-07T07:51:00Z | PIT=PIT_SAFE
- usd_empsit_2026-08-07 | INDIVIDUAL_FORECAST | nonfarm_payroll_change=18000 persons | Vanguard | pub=2026-08-07T07:51:00Z | PIT=PIT_SAFE
All 3 employment events have Reuters and/or FactSet pre-release NFP/u-rate numbers. usd_empsit_2026-08-07 also has PIT_SAFE Dow Jones 83k / 4.2% via IBTimes (08:51 BST). usd_empsit_2026-02-11 is the CES-benchmark official event; consensus still targets the headline first print, not the benchmark restatement. AHE coverage is incomplete (present on Aug 2025 Reuters; YoY only on Jul 2026 Reuters; missing on official Jul 2026 values so that series cannot join).

FOMC RESULTS
------------
- usd_fomc_statement_2025-09-17 | SURVEY_CONSENSUS | expected_policy_decision=cut_25bp categorical | Reuters | pub=2025-09-11T12:40:00Z | PIT=PIT_SAFE
- usd_fomc_statement_2026-01-28 | SURVEY_CONSENSUS | expected_policy_decision=hold categorical | Reuters | pub=2026-01-21T14:02:00Z | PIT=PIT_SAFE
- usd_fomc_statement_2026-01-28 | MARKET_IMPLIED_EXPECTATION | market_implied_cut_probability=0.03 probability | Federal Funds futures via FXStreet | pub=2026-01-28T09:30:05Z | PIT=PIT_SAFE
- usd_fomc_statement_2026-07-29 | SURVEY_CONSENSUS | expected_policy_decision=hold categorical | FactSet | pub=2026-07-29T13:38:00Z | PIT=PIT_SAFE
- usd_fomc_statement_2026-07-29 | MARKET_IMPLIED_EXPECTATION | market_implied_hike_probability=0.36 probability | CME FedWatch via CBS News | pub=2026-07-29T13:38:00Z | PIT=PIT_SAFE
FOMC is not forced into CPI/NFP schema. Survey decisions and market-implied probabilities are stored separately. Reuters Sep 8-11 poll: 105/107 expect -25bp, 2 expect -50bp (PIT_SAFE vs FOMC T0). Reuters Jan 16-21 poll: 100/100 hold (PIT_SAFE). FXStreet 2026-01-28T09:30:05Z: FF futures cut odds <3% (PIT_SAFE, MARKET_IMPLIED). CBS 2026-07-29 09:38 EDT: FactSet survey hold plus FedWatch 36% hike (PIT_SAFE). Probabilities were not converted into a scalar consensus of -25bp or +25bp.

PILOT COVERAGE MATRIX
---------------------
| event | family | T0 | sources_found | PIT_safe_sources | series_covered | publication_time_proven | artifact_hashed | official_join_valid | raw_surprise_possible |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| usd_cpi_2025-09-11 | CPI | 2025-09-11T12:30:00Z | 2 | 0 | core_mom,core_yoy,headline_mom,headline_yoy | False | True | False | False |
| usd_cpi_2026-02-13 | CPI | 2026-02-13T13:30:00Z | 2 | 0 | core_mom,core_yoy,headline_mom,headline_yoy | True | True | False | False |
| usd_cpi_2026-07-14 | CPI | 2026-07-14T12:30:00Z | 2 | 0 | core_mom,core_yoy,headline_mom,headline_yoy | True | True | False | False |
| usd_empsit_2025-09-05 | EMPLOYMENT_SITUATION | 2025-09-05T12:30:00Z | 2 | 0 | average_hourly_earnings_mom,average_hourly_earnings_yoy,nonfarm_payroll_change,unemployment_rate | True | True | False | False |
| usd_empsit_2026-02-11 | EMPLOYMENT_SITUATION | 2026-02-11T13:30:00Z | 2 | 0 | nonfarm_payroll_change,unemployment_rate | True | True | False | False |
| usd_empsit_2026-08-07 | EMPLOYMENT_SITUATION | 2026-08-07T12:30:00Z | 3 | 1 | average_hourly_earnings_yoy,nonfarm_payroll_change,unemployment_rate | True | True | True | True |
| usd_fomc_statement_2025-09-17 | FOMC | 2025-09-17T18:00:00Z | 1 | 1 | expected_policy_decision | True | True | True | True |
| usd_fomc_statement_2026-01-28 | FOMC | 2026-01-28T19:00:00Z | 2 | 2 | expected_policy_decision,market_implied_cut_probability | True | True | True | True |
| usd_fomc_statement_2026-07-29 | FOMC | 2026-07-29T18:00:00Z | 1 | 1 | expected_policy_decision,market_implied_hike_probability | True | True | True | True |

SOURCE QUALITY MATRIX
---------------------
| publisher | source type | historical discoverability | publication timestamp quality | consensus semantics quality | artifact/vintage quality | automation feasibility | access limitations | overall PIT usefulness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Reuters | news + economist survey | HIGH (dated slugs, morning previews, dedicated polls) | HIGH original UTC clock; MEDIUM because of untimed same-day Updated | HIGH (survey of economists; range often printed) | Excerpt-only here (licensing); full HTML not stored | PARTIAL (URL pattern on T0 morning) | Paywall on some desks; no illicit mirrors | HIGH with WARC/last-mod |
| FactSet Insight | survey median blog | HIGH (stable month-named URLs) | MEDIUM (calendar date + Tomorrow; no clock) | HIGH for YoY NSA; often no MoM; n sometimes 3-15 | Excerpt-only; live page could be edited | HIGH URL pattern | Marketing pages; n can be tiny | HIGH if captured day-before at known UTC |
| Morningstar | news relaying FactSet + individual banks | MEDIUM | MEDIUM date-only | MIXED (FactSet consensus plus INDIVIDUAL_FORECAST) | Excerpt-only | LOW | None observed | MEDIUM |
| IBTimes UK | news relaying Dow Jones | MEDIUM | HIGH (BST clock) | HIGH for DJ poll; also reports other panels | Excerpt-only | LOW | Secondary publisher | MEDIUM-HIGH as a clocked DJ relay |
| CBS News | news relaying FactSet + FedWatch | MEDIUM | HIGH when Updated clock present | MIXED (survey vs market-implied must stay separate) | Excerpt-only | LOW | 406 on another CBS FOMC URL in this pilot | MEDIUM-HIGH when clocked |
| FXStreet | analysis citing FF futures | MEDIUM | HIGH (GMT clock in byline) | MARKET_IMPLIED not survey | Excerpt-only | LOW | Preview later overwritten on some FXStreet news URLs | MEDIUM for implied odds |
| CME FedWatch live tool | market-implied | HIGH today, POOR historically without a dated snapshot | N/A unless contemporaneously quoted | Probability distribution | Not archived here | Requires historical snapshots | Do not reconstruct from today | USEFUL only via contemporaneous citation or official archive |
| Bloomberg | news | HIGH | HIGH when accessible | HIGH | Not opened (paywall) | LOW without license | Paywall; no bypass | UNKNOWN in this pilot |
| Wayback CDX | archive | attempted | timeout in this session | n/a | n/a | PARTIAL | Timeouts | NOT USED |

PIT REJECTIONS
--------------
- CBS Sep 17 2025 FOMC URL: HTTP 406 — access limitation, not used.
- Bloomberg Jan 28 2026 decision-day guide: paywall, not opened.
- Reuters post-release actuals articles (e.g. Sep 11 2025 CPI wrap 'economists had forecast'): REJECT_POST_RELEASE as primary vintage even if they quote the same survey.
- FOMC minutes (released weeks later) describing pre-meeting market odds: REJECT_POST_RELEASE as the evidence timestamp.
- TradingKey / SEO / crypto FedWatch blogs: REJECT_UNSOURCED or not opened as primary.
- Search snippets: discovery only.
- Live CME FedWatch today: not a historical vintage.
- Same-day Reuters BLS previews: not REJECT, but PIT_SAFE_WITH_LIMITATION because Updated lacks intra-day last-mod.

MULTI-SOURCE DISAGREEMENT
-------------------------
Not averaged. Descriptive only.
- Aug 2025 NFP: Reuters 75k vs FactSet 80k. U-rate Reuters 4.3 vs FactSet 4.2.
- Jan 2026 CPI headline YoY: Reuters 2.5 vs FactSet 2.4 (FactSet n=12, range 2.30-2.70).
- Jan 2026 NFP: Reuters 70k (range -10k to 135k) vs FactSet 75k (n=15, range 50k-85k).
- Jun 2026 core CPI YoY: Reuters 2.8 vs FactSet 2.9.
- Jul 2026 NFP: Reuters 80k vs Dow Jones 83k vs FactSet 97.5k (n=12). Individual Vanguard 18k stored separately.
Disagreement is data. No house consensus invented.

OFFICIAL ACTUAL JOIN PROOF
--------------------------
- usd_fomc_statement_2025-09-17 expected_policy_decision forecast=cut_25bp actual=-25 join=True surprise_possible=True (Categorical survey mapped only via stored expected_change_bp. Probability distribution not collapsed.)
- usd_fomc_statement_2026-01-28 expected_policy_decision forecast=hold actual=0 join=True surprise_possible=True (Categorical survey mapped only via stored expected_change_bp. Probability distribution not collapsed.)
- usd_fomc_statement_2026-01-28 market_implied_cut_probability forecast=0.03 actual=0 join=True surprise_possible=False (Market-implied probability retained. Not converted to a scalar consensus rate change. No surprise_raw.)
- usd_empsit_2026-08-07 nonfarm_payroll_change forecast=83000 actual=-23000 join=True surprise_possible=True (Pipeline proof only. No z-score. No FX join.)
- usd_empsit_2026-08-07 unemployment_rate forecast=4.2 actual=4.1 join=True surprise_possible=True (Pipeline proof only. No z-score. No FX join.)
- usd_empsit_2026-08-07 nonfarm_payroll_change forecast=18000 actual=-23000 join=True surprise_possible=False (Joinable but individual forecast is not consensus; surprise not computed as consensus surprise.)
- usd_fomc_statement_2026-07-29 expected_policy_decision forecast=hold actual=0 join=True surprise_possible=True (Categorical survey mapped only via stored expected_change_bp. Probability distribution not collapsed.)
- usd_fomc_statement_2026-07-29 market_implied_hike_probability forecast=0.36 actual=0 join=True surprise_possible=False (Market-implied probability retained. Not converted to a scalar consensus rate change. No surprise_raw.)

RAW SURPRISE PIPELINE PROOF
---------------------------
Formula (PIT_SAFE + matching official first print + matching units only): surprise_raw = official_first_print_actual - pre_release_consensus.
No z-score. No FX. Individual forecasts excluded from consensus surprise.
- usd_fomc_statement_2025-09-17 expected_policy_decision: 0.0
- usd_fomc_statement_2026-01-28 expected_policy_decision: 0.0
- usd_empsit_2026-08-07 nonfarm_payroll_change: -106000.0
- usd_empsit_2026-08-07 unemployment_rate: -0.10000000000000053
- usd_fomc_statement_2026-07-29 expected_policy_decision: 0.0

CAN WE SCALE TO ALL 29 EVENTS?
PARTIAL
EVENTS WITH PIT-SAFE CONSENSUS:
4 / 9
SERIES WITH PIT-SAFE CONSENSUS:
usd_empsit_2026-08-07:nonfarm_payroll_change (INDIVIDUAL_FORECAST); usd_empsit_2026-08-07:nonfarm_payroll_change (SURVEY_CONSENSUS); usd_empsit_2026-08-07:unemployment_rate (SURVEY_CONSENSUS); usd_fomc_statement_2025-09-17:expected_policy_decision (SURVEY_CONSENSUS); usd_fomc_statement_2026-01-28:expected_policy_decision (SURVEY_CONSENSUS); usd_fomc_statement_2026-01-28:market_implied_cut_probability (MARKET_IMPLIED_EXPECTATION); usd_fomc_statement_2026-07-29:expected_policy_decision (SURVEY_CONSENSUS); usd_fomc_statement_2026-07-29:market_implied_hike_probability (MARKET_IMPLIED_EXPECTATION)
EVENTS WITH RAW SURPRISE COMPUTABLE:
4 / 9
FOMC EXPECTATION PROVEN:
3 / 3
BIGGEST BLOCKERS:
- Same-day Reuters 'Updated' without last-mod clock (blocks PIT_SAFE on otherwise clocked BLS previews)
- FactSet day-before pages lack UTC clocks
- Full-page archival/licensing (excerpts hashed, not WARC)
- Paywalls (Bloomberg) and HTTP 406 (some CBS)
- No CME FedWatch historical vintage API used; only contemporaneous citations
- Thin FactSet panels (n=4) and missing AHE on some official value rows
- Wayback CDX timeout in this session
RECOMMENDED STAGE 2 CONSENSUS ACTION:
Capture Reuters morning previews and FactSet Insight pages into dated WARC/last-mod hashes at a known UTC before each remaining T0; license or skip Bloomberg; keep Reuters/FactSet/Dow Jones as separate vintages; store FOMC survey distributions and FedWatch citations without collapsing to a single bp; do not scrape SEO calendars.
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
FILES CHANGED:
research helpers/tests/report/new consensus pilot data only
STOP.
