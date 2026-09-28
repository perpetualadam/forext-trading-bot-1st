# MACRO RESEARCH — STAGE 2
# COMPLETE US PIT MACRO ARCHIVE FOR VERIFIED FX WINDOW

Status: STAGE 2 DATASET COMPLETE — research-only.
Stage-1 rules in `reports/decision_quality/macro_official_pit_stage1.md` are preserved.
No production collector. No trading-bot change. No model. No surprise. No FX signal test.

Official sources only: BLS CPI and Employment Situation archived news releases; Federal Reserve / FOMC policy statements.
Current BLS/FRED time series were not used as first prints.
Existing `data/research/macro_first_print/` originals were copied, not modified.
V2 observations/outcomes/market files and historical FX CSVs were not modified.

Storage: `data/research/macro/us_pit/` (`raw/`, `events/`, `manifest/`).

---

US PIT ARCHIVE WINDOW:
2025-09-01T00:00:00Z through 2026-08-31T23:50:00Z
(verified M5 FX cache; six pairs with bid/ask)

CPI:
expected: 11 published releases with scheduled timestamps in-window (plus 1 officially unpublished October 2025 reference month)
archived: 10
missing: 1 officially unpublished (October 2025, no news release) + 1 RETRIEVAL_BLOCKED (`usd_cpi_2026-08-12`, July 2026 reference; official HTML `cpi_08122026.htm` returned BLS 403 Access Denied; current-edition page not substituted)
irregular: `usd_cpi_2025-12-18` — 2-month SA change Sep→Nov 2025; `headline_mom` / `core_mom` left missing; stored as `headline_2m_sa` / `core_2m_sa` = +0.2. Lapse-delayed but otherwise standard: `usd_cpi_2025-10-24`.

EMPLOYMENT:
expected: 11 published (plus 1 officially unpublished October 2025)
archived: 11
missing: 1 officially unpublished October 2025 Employment Situation news release (no first-print event invented; later CES October figures appearing in revision paragraphs stay on later events)
revision chains: August 2025 NFP first print on `usd_empsit_2025-09-05` remains +22,000. `usd_empsit_2025-11-20` records August previously +22,000 revised to -4,000. `usd_empsit_2025-12-16` records August previously -4,000 revised to -26,000. First print was not overwritten.
Other irregulars (values still first-print where stated): `usd_empsit_2026-01-09` CPS seasonal revision applied (household rates “as first published” vs “as revised”); `usd_empsit_2026-02-11` CES annual benchmark tables reflect March 2025 benchmark. Lapse-delayed September print: `usd_empsit_2025-11-20`. Some 2026 AHE YoY fields are missing in the lead and were left missing.

FOMC:
expected: 8 policy-statement events (Sep 17, Oct 29, Dec 10 2025; Jan 28, Mar 18, Apr 29, Jun 17, Jul 29 2026). Sep 15–16 2026 is after the FX window.
archived: 8
missing: 0
Decisions: three 25bp cuts to 4.00–4.25, 3.75–4.00, 3.50–3.75, then five holds at 3.50–3.75. Press conference URLs and minutes dates stored in `events/fomc_related.json` and are not merged into the statement timestamp.

TOTAL EVENTS:
32 inventory rows (29 ARCHIVED + 2 OFFICIALLY_UNPUBLISHED + 1 RETRIEVAL_BLOCKED)
TOTAL VALUE RECORDS:
161
RAW ARTIFACTS:
29
UNIQUE HASHES:
29
PIT VALIDATION:
unique macro_event_id: pass
unique value_id within archive: pass
no duplicate family+timestamp: pass
hash present on every ARCHIVED artifact: pass
DST-aware UTC (08:30 ET and 14:00 ET, EST vs EDT): pass
reference period distinct from release month for BLS: pass
consensus and consensus_asof_utc null on all values: pass
validation_problems: {}

REVISION VALIDATION:
August 2025 NFP first print stays +22,000 on `usd_empsit_2025-09-05`.
Later vintages are separate value rows (`nfp_revision_august`) on later events (-4,000 then -26,000).
No first-print overwrite detected.

CONSENSUS:
NULL / NOT AVAILABLE

FX COVERAGE:
Coverage/integrity only. No signal performance.
T0 = scheduled_release_utc. Containing M5 start = floor_m5(T0). Last completed bar = floor_m5(T0) − 5m (the candle containing T0 is not known before T0).
Windows checked: -240/-120/-60/-30/-15/-5 and +5/+15/+30/+60/+120/+240 minutes, all six pairs, genuine bar presence in `data/historical/*_M5.csv`.
Result: every event with a scheduled timestamp (29 archived + 1 blocked CPI clock) has last-completed bar and all 12 windows present on all six pairs. Unpublished October 2025 rows have no T0 and no coverage join.

RETRIEVAL BLOCKERS:
- `usd_cpi_2026-08-12` — https://www.bls.gov/news.release/archives/cpi_08122026.htm — BLS Access Denied (403) on two official-page retrieval attempts. Direct scripted GET was not used to bypass bot policy. PDF on the BLS archive index was not substituted as a silent third-party copy. Event remains RETRIEVAL_BLOCKED with official schedule clock 2026-08-12T12:30:00Z (08:30 EDT).

AMBIGUOUS VALUES REJECTED:
[] (no table-vs-lead mismatches required dropping a whole event). Missing ordinary MoM on the November 2025 CPI 2-month print is preserved as missing, not rejected-as-invented. Missing AHE YoY on some 2026 Employment leads left missing.

CAN THIS DATASET BE USED FOR EVENT-CONDITIONED FX RESEARCH?
PARTIAL
YES for the 29 hashed events whose T0 and M5 windows are complete. PARTIAL because October 2025 CPI/Employment have no official release timestamp, and July 2026 CPI (released 2026-08-12) has a clock but no archived first print.

CAN THIS DATASET BE USED FOR ACTUAL-FIRST-PRINT RESEARCH?
PARTIAL
YES for 10 CPI + 11 Employment + 8 FOMC hashed official artifacts under PIT_SAFE_IF_USING_ARCHIVED_RELEASE. PARTIAL until the blocked August 12 2026 CPI archive is stored, and because October 2025 prints do not exist.

CAN THIS DATASET BE USED FOR SURPRISE RESEARCH?
NO

PRODUCTION CHANGE:
NO
V2 POLICY CHANGE:
NO
MODEL TRAINED:
NO
OANDA/API REQUESTS:
0
FILES CHANGED:
- reports/decision_quality/_macro_us_pit_stage2.py
- reports/decision_quality/macro_us_pit_stage2.md
- tests/test_macro_us_pit_stage2.py
- data/research/macro/us_pit/README.md
- data/research/macro/us_pit/manifest/inventory.json
- data/research/macro/us_pit/manifest/summary.json
- data/research/macro/us_pit/events/macro_event.json
- data/research/macro/us_pit/events/macro_event_value.json
- data/research/macro/us_pit/events/fx_coverage.json
- data/research/macro/us_pit/events/fomc_related.json
- data/research/macro/us_pit/raw/bls/cpi/* (copied 2025 official.txt + 2026 converted archives, excluding blocked August 2026)
- data/research/macro/us_pit/raw/bls/employment/* (copied 2025 official.txt + 2026 converted archives)
- data/research/macro/us_pit/raw/fomc/* (hashed official statement texts)
STOP.
