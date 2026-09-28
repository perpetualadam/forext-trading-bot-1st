# MACRO RESEARCH — STAGE 1
# OFFICIAL US HISTORICAL SOURCE DISCOVERY + POINT-IN-TIME AUDIT

Status: STAGE 1 COMPLETE — source discovery + PIT audit only.
No production collector. No trading-bot change. No model. No trading rule.
No surprise series. No FX join executed.

Official sources used: BLS news-release archives and year schedule; Federal Reserve / FOMC statements, implementation notes, and meeting calendars.
Not used: blogs, Wikipedia, economic calendars, SEO calendars, scraped reposts, FRED/ALFRED current series as first prints, commercial consensus.

---

FX RESEARCH WINDOW
------------------
earliest: 2025-09-01T00:00:00Z
latest: 2026-08-31T23:50:00Z
symbols: EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF
price types: mid OHLCV (`open`/`high`/`low`/`close`/`volume`) plus genuine bid and ask OHLC (`bid_*`, `ask_*`); all rows `complete=True`
coverage notes:
- Verified from `data/historical/{EUR,GBP,USD_JPY,AUD,USD_CAD,USD_CHF}_USD_M5.csv`, not assumed from prior reports. Matches `reports/decision_quality/baseline_12m_quant_offline.md` and `quant_v2_research_plan.md` DEV0.
- Bar counts: EUR 74572, GBP 74555, JPY 74557, AUD 74563, CAD 74560, CHF 74514.
- Gaps >5.5 minutes: 73 / 87 / 85 / 81 / 82 / 116 by pair. Max gap 2945 minutes (~49 hours) — weekend/holiday FX close, not missing-month holes.
- Macro history required for this FX window is therefore scheduled US releases from early September 2025 through 31 August 2026. Releases after 2026-08-31 (for example 2026-09-04 Employment for August 2026, 2026-09-11 CPI for August 2026) fall outside usable M5.

This is the macro window we actually need. Official 2025 first-print HTML already stored under `data/research/macro_first_print/` covers calendar-year 2025 only and was **not** modified. 2026 BLS HTML archives exist (spot-checked `cpi_01132026.htm`, embargo 08:30 ET Tuesday January 13 2026, USDL-26-0042) but were not bulk-downloaded in this stage.

CPI
---
official source: U.S. Bureau of Labor Statistics CPI news release. Schedule: https://www.bls.gov/schedule/2026/ (and 2025 year page). Archive index: https://www.bls.gov/bls/news-release/cpi.htm. Dated HTML: `https://www.bls.gov/news.release/archives/cpi_MMDDYYYY.htm`. Embargo line plus USDL number is on the release itself.
archive: YES. Index lists PDF for 2025–2026; HTML archive URLs still resolve and contain the news-release lead. TXT archives stop in the mid-2000s. October 2025 CPI is officially unpublished (appropriations lapse). Direct scripted GET to bls.gov has historically returned Akamai 403; official pages are reachable through a browser/gateway and were already converted+hashed for 2025.
timestamp quality: SCHEDULED 08:30 America/New_York from the BLS calendar AND the embargo line on the archived release. DST-aware conversion via `ZoneInfo("America/New_York")` (EDT → 12:30Z, EST → 13:30Z). `published_release_utc` (measured wire time) is NOT independently available from BLS. Webpage modification time is not the release time.
first-print recoverability: YES from the archived release document for headline CPI MoM SA, headline CPI YoY NSA, core CPI MoM SA, core CPI YoY NSA when the lead states a standard 1-month change. Previous-as-known is recoverable when the lead says “after rising/falling X”. November 2025 CPI (released 2025-12-18) is a 2-month SA change Sep→Nov because October was not collected — `headline_cpi_mom_sa` / `core_cpi_mom_sa` must stay missing, not invented. Current BLS/FRED time series = CURRENT_VALUE_ONLY / REVISION_RISK.
revision handling: CPI monthly percent changes in later databases can differ from the print in the original release. Keep the archived document as first print. Never overwrite. BLS archive index itself warns that archived releases may have been revised in subsequent releases — that is why the dated HTML (or hashed conversion) is the vintage, not today’s database.
PIT verdict: PIT_SAFE_IF_USING_ARCHIVED_RELEASE for values printed in a dated archived news release. CURRENT_VALUE_ONLY / REVISION_RISK if taken from a live series API. UNKNOWN for actual wire publication time.

EMPLOYMENT / NFP
----------------
official source: BLS Employment Situation (CES establishment + CPS household). Archive index: https://www.bls.gov/bls/news-release/empsit.htm. Dated HTML: `https://www.bls.gov/news.release/archives/empsit_MMDDYYYY.htm`.
archive: YES. Same PDF-index / HTML-URL pattern as CPI. October 2025 Employment Situation officially unpublished (lapse). 2026 PDFs listed through August on the index.
timestamp quality: same as CPI — scheduled/embargo 08:30 ET, DST-aware UTC. No independent actual_publication_time.
first-print recoverability: YES from the archived release for current-month NFP change, unemployment rate, and AHE MoM/YoY when the lead states them. Must keep separate fields: `nfp_change_first_print`, `previous_nfp_as_previously_reported`, `previous_nfp_revised`, `revision_amount`. Do not collapse into one “NFP” field.
revision handling: CES revises the prior two months in every subsequent release. Smoking-gun chain in this window:
- 2025-09-05 first print of August NFP = +22,000
- 2025-11-20 revises August from +22,000 to -4,000
- 2025-12-16 revises August from -4,000 to -26,000
The +22,000 stays on `usd_empsit_2025-09-05`. Later vintages are new records on later events.
PIT verdict: PIT_SAFE_IF_USING_ARCHIVED_RELEASE for first prints and for revisions *as presented in that later release*. REVISION_RISK if a current PAYEMS/UNRATE series is treated as the historical print.

FOMC
----
official source: Board of Governors of the Federal Reserve System. Calendar: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm. Statements: `/newsevents/pressreleases/monetaryYYYYMMDDa.htm`. Implementation notes: `...a1.htm`. Press conferences and minutes are separate URLs/dates.
archive: YES. Dated HTML statements and implementation notes remain posted. Calendar lists 2025 and 2026 meetings, minutes release dates, SEP/dot-plot meetings (*), and press-conference links.
timestamp quality: statement pages print “For release at 2:00 p.m. EDT” or “EST”. Convert with America/New_York, not fixed EST. Example: 2025-09-17 14:00 EDT = 18:00Z; 2025-12-10 14:00 EST = 19:00Z. Calendar does not by itself prove intra-day clock; the statement header does. No independent measured wire time. Minutes have their own later release dates (typically ~3 weeks). Press conference is a separate same-day information event and MUST NOT share the statement timestamp as if it were one event.
decision recoverability: YES from the statement (change in the target range) plus implementation note (explicit target range in the Desk directive). Proof sample: Sep 17 2025 cut 25bp to 4.00–4.25; Oct 29 cut 25bp to 3.75–4.00; Dec 10 cut 25bp to 3.50–3.75. Previous range recoverable from the stated 25bp change and/or the prior meeting’s hashed statement.
separate statement/press conference/minutes: YES — kept as separate event families / URLs / dates. SEP/dot plot inventoried only (quarterly * meetings). Not modeled in this stage.
PIT verdict: PIT_SAFE_IF_USING_ARCHIVED_RELEASE for the hashed dated statement + implementation note. Live re-fetch of HTML without a stored hash is UNCERTAIN (silent edit not disproven). Rate decisions are not CES monthly revisions.

SOURCE RELIABILITY MATRIX
-------------------------
| event family | official source | historical archive available | exact release timestamp available | first print recoverable | previous-as-known recoverable | revision history recoverable | consensus available | PIT status | automation feasibility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CPI | BLS news release + year schedule | YES (HTML archive URL + PDF on index; Oct 2025 unpublished) | SCHEDULED 08:30 ET yes; actual wire no | YES from archived lead (MoM missing on Nov 2025 2-month print) | YES when lead states prior month | PARTIAL (later releases / current DB are not a vintage API; keep each archive) | NO — CONSENSUS NOT AVAILABLE FROM THIS SOURCE | PIT_SAFE_IF_USING_ARCHIVED_RELEASE | PARTIAL (URL pattern known; direct GET often 403; parse lead + embargo) |
| Employment / NFP | BLS Employment Situation | YES (same pattern; Oct 2025 unpublished) | SCHEDULED 08:30 ET yes; actual wire no | YES (NFP, u-rate, AHE when stated) | YES from CES revision paragraph | YES as presented on later releases; never overwrite first print | NO — CONSENSUS NOT AVAILABLE FROM THIS SOURCE | PIT_SAFE_IF_USING_ARCHIVED_RELEASE | PARTIAL (same 403/gateway constraint) |
| FOMC | Federal Reserve Board / FOMC | YES (dated statement HTML, implementation notes, calendars, minutes, press-conference pages) | SCHEDULED 14:00 ET on statement yes; actual wire no; minutes/press separate | YES target range + change | YES from prior statement / implied by stated change | N/A as CES-style monthly revision; hash required against silent HTML edit | NO — CONSENSUS NOT AVAILABLE FROM THIS SOURCE | PIT_SAFE_IF_USING_ARCHIVED_RELEASE | YES for HTML fetch of federalreserve.gov in this audit; still hash on ingest |

PROOF SAMPLE
------------
Location: `data/research/macro/pit_proof/` (NEW). Existing `data/research/macro_first_print/` and all V2 JSONL/market files were not modified.

CPI:
1. `usd_cpi_2025-09-11` ref 2025-08; scheduled 2025-09-11T12:30:00Z; USDL-25-1356; headline MoM +0.4 (prev +0.2), YoY +2.9 (prev +2.7), core MoM +0.3, core YoY +3.1. Archive https://www.bls.gov/news.release/archives/cpi_09112025.htm sha256 `b26593eb25ba8638074c96ca805af459c4d05c4244b2eaee75c88ef3de5c41ca`. PIT_SAFE_IF_USING_ARCHIVED_RELEASE.
2. `usd_cpi_2025-10-24` ref 2025-09; scheduled 2025-10-24T12:30:00Z; USDL-25-1502; MoM +0.3 (prev +0.4), YoY +3.0, core MoM +0.2 (prev +0.3), core YoY +3.0. Lapse-delayed relative to usual mid-month clock; September collection completed before the lapse.
3. `usd_cpi_2025-12-18` ref 2025-11; scheduled 2025-12-18T13:30:00Z; USDL-25-1584; 2-month SA +0.2 Sep→Nov; YoY +2.7; core 2-month +0.2; core YoY +2.6. `headline_cpi_mom_sa` = missing (not a 1-month first print).

Employment:
1. `usd_empsit_2025-09-05` ref 2025-08; 2025-09-05T12:30:00Z; USDL-25-1344; NFP first print +22,000; u-rate 4.3; AHE MoM +0.3 / YoY +3.7; July previously +73,000 revised to +79,000 (+6,000). sha256 `c1f41b5d4fda76cd9eb0d7df76640e990e1053a461679aabdda01357f25efcf7`.
2. `usd_empsit_2025-11-20` ref 2025-09; 2025-11-20T13:30:00Z; USDL-25-1487; NFP +119,000; u-rate 4.4; AHE MoM +0.2; August previously +22,000 revised to -4,000.
3. `usd_empsit_2025-12-16` ref 2025-11; 2025-12-16T13:30:00Z; USDL-25-1581; NFP +64,000; u-rate 4.6 vs September (no October household print); AHE MoM +0.1 / YoY +3.5; August -4,000 → -26,000; September +119,000 → +108,000.

FOMC:
1. `usd_fomc_statement_2025-09-17` meeting 2025-09-16/17; statement 2025-09-17T18:00:00Z (14:00 EDT); target 4.00–4.25; -25bp; previous 4.25–4.50. Implementation note confirms Desk range 4 to 4-1/4 effective Sep 18. Press conference and minutes 2025-10-08 are separate.
2. `usd_fomc_statement_2025-10-29` 2025-10-29T18:00:00Z (14:00 EDT); target 3.75–4.00; -25bp. Minutes 2025-11-19 separate.
3. `usd_fomc_statement_2025-12-10` 2025-12-10T19:00:00Z (14:00 EST); target 3.50–3.75; -25bp. Minutes 2025-12-30 separate.

LOOKAHEAD AUDIT
---------------
For every proof event:

| event | Could this exact value have been known at the stated release time? | Could a backtest accidentally read a later revision? | Does the source preserve enough vintage to prevent that? |
| --- | --- | --- | --- |
| usd_cpi_2025-09-11 | YES | NO if using this hashed archive | YES |
| usd_cpi_2025-10-24 | YES | NO if using this hashed archive | YES |
| usd_cpi_2025-12-18 | YES for 2-month/YoY prints; MoM not claimed | NO if using this hashed archive | YES |
| usd_empsit_2025-09-05 | YES | NO for +22,000 on this event (later -4k/-26k belong on later events) | YES |
| usd_empsit_2025-11-20 | YES | NO if using this hashed archive | YES |
| usd_empsit_2025-12-16 | YES | NO if using this hashed archive | YES |
| usd_fomc_statement_2025-09-17 | YES | NO for the hashed excerpt; UNCERTAIN if live HTML is re-fetched without hash | YES for hashed excerpt |
| usd_fomc_statement_2025-10-29 | YES | NO for hashed excerpt; UNCERTAIN on live re-fetch | YES for hashed excerpt |
| usd_fomc_statement_2025-12-10 | YES | NO for hashed excerpt; UNCERTAIN on live re-fetch | YES for hashed excerpt |

Using today’s BLS/FRED “latest” series for any of these would flip the middle column to YES (lookahead via revision). That path is not approved.

No UNCERTAIN remains on the hashed proof-sample records. UNCERTAIN applies only to unhashed live HTML re-fetch, which is not approved for later modeling.

CONSENSUS GAP
-------------
WHAT OFFICIAL SOURCES CANNOT PROVIDE

BLS news releases and Federal Reserve / FOMC statements, implementation notes, minutes, and SEP materials do **not** publish a pre-release market consensus forecast.

CONSENSUS NOT AVAILABLE FROM THIS SOURCE

Do not substitute: previous value, Fed/SEP staff forecast, a survey mentioned after release, latest third-party historical consensus, or analyst commentary.

Without PIT consensus, later analyses that remain valid:
- event-conditioned realized volatility
- pre/post release M5 movement
- cross-pair USD response
- MFE/MAE around T0
- continuation vs reversal after T0
- dispersion across the six USD pairs

Not valid yet:
- surprise = actual − consensus

PROPOSED MACRO SCHEMA
---------------------
Normalized, vintage-preserving. Not implemented in production.

`macro_event`
- macro_event_id
- source
- country / currency
- event_family (CPI | EMPLOYMENT_SITUATION | FOMC)
- reference_period
- scheduled_release_utc
- published_release_utc (nullable; unknown for these official sources)
- source_timezone
- source_document_id (USDL number or FOMC statement id)
- source_document_date
- source_url_or_reference
- source_vintage
- raw_document_hash
- ingested_at_utc / observed_at_utc
- pit_status

`macro_event_value` (many rows per one release)
- macro_event_id (FK)
- event_name
- source_series_id (nullable)
- actual_first_print
- previous_as_reported
- previous_revised
- revision_amount
- unit / seasonal_adjustment / frequency
- consensus / consensus_asof_utc (both null unless a proven PIT consensus source is added later)
- pit_status

FOMC extras on the event or as values: meeting_date, ff_target_lower, ff_target_upper, ff_target_change_bp, ff_previous_lower, ff_previous_upper. Statement vs press conference vs minutes vs SEP are **separate events**, never one timestamp.

One CPI release is one event with multiple value records (headline MoM/YoY, core MoM/YoY). Same for Employment Situation.

IMMUTABILITY RULES
------------------
1. Never overwrite a historical observation.
2. Never replace a first print with a revised value.
3. A new revision is a new vintage or an explicit revision record on a later event.
4. Raw source artifact must be hashable (`raw_document_hash`).
5. Store `ingested_at_utc` / `observed_at_utc` separately from `scheduled_release_utc` / `published_release_utc`.
6. Preserve enough provenance to reproduce every derived value (URL, USDL/statement id, hash, parser locator).
7. Consensus must carry `consensus_asof_utc`. No `consensus_asof_utc` ⇒ not valid for surprise backtesting.
8. Missing stays missing (November 2025 CPI MoM; October 2025 unpublished releases).
9. Do not treat webpage mtime as economic release time.

FUTURE FX JOIN DESIGN
---------------------
Not executed in this stage.

T0 = `scheduled_release_utc` until a true `published_release_utc` exists.

Pre windows: -240, -120, -60, -30, -15, -5 minutes.
Post windows: +5, +15, +30, +60, +120, +240 minutes.

Use genuine bid/ask. BUY path ask → future bid_close; SELL path bid → future ask_close. No mid fallback.

M5 lookahead rule:
- An M5 bar is labeled by its **start** timestamp in this cache (`2025-09-01T00:00:00Z` is the 00:00–00:05 bar).
- The candle that **contains** T0 is not known before T0. Example: CPI T0 = 12:30Z lives inside `12:30:00Z` (12:30–12:35). That bar’s close is 12:35Z information.
- Last completed bar strictly before T0: `floor_m5(T0) - 5m` if T0 is exactly on a boundary, else `floor_m5(T0) - 5m` still, because the in-progress bar is not complete. Equivalently: last bar with `bar_start + 5m <= T0`.
- First post bar: first bar with `bar_start >= T0` is still in-progress at T0 if T0 is inside it; first **completed** post information is the close of the containing bar, which is after T0.
- Pre-window features may use only completed bars ending at or before T0. Post-window outcomes start after T0, never including the containing bar’s close as if it were known at T0.
- Weekend gaps: if T0 is Friday 14:00 ET, +240m may land in Saturday empty tape; drop or flag rather than interpolating.

CAN WE SAFELY BUILD OUR OWN HISTORICAL ACTUAL/REVISION DATASET?
PARTIAL

YES for official archived BLS CPI and Employment Situation HTML (and PDF) first prints plus CES revisions as printed on later releases, with hashed artifacts and the immutability rules above. YES for FOMC dated statements and implementation notes with hashed copies. PARTIAL because: (1) this proof covers 3+3+3 events, not the full Sep 2025–Aug 2026 window; (2) 2026 BLS archives are listed and HTML spot-checked but not yet stored; (3) October 2025 CPI and Employment are officially unpublished; (4) November 2025 CPI has no standard MoM first print; (5) actual wire time is unavailable; (6) direct BLS GET automation is 403-prone.

CAN WE SAFELY BUILD HISTORICAL CONSENSUS FROM THESE OFFICIAL SOURCES?
NO

CAN SURPRISE BE BACKTESTED YET?
NO

NEXT RECOMMENDED MACRO STEP
---------------------------
Collect remaining official BLS CPI and Employment Situation archived releases whose scheduled times fall inside 2025-09-01Z–2026-08-31Z (plus FOMC statements/implementation notes in that window), store raw+hash, parse into `macro_event` / `macro_event_value`, and do **not** compute surprise. Consensus remains a separate vendor/PIT problem. Do not start ECB/Eurostat/ONS/BoJ/RBA/BoC/SNB until this US vintage store exists.

The same event/value/hash/immutability architecture can later extend to EUR, GBP, JPY, AUD, CAD, CHF official sources. Not implemented here.

PIT CLASSIFICATION KEY
----------------------
- PIT_SAFE: not claimed for these official sources’ live APIs.
- PIT_SAFE_IF_USING_ARCHIVED_RELEASE: value is printed on a dated official archive whose bytes/hash we store.
- CURRENT_VALUE_ONLY: today’s BLS/FRED/current-edition page.
- REVISION_RISK: using a later vintage as if it were the first print (classic NFP lookahead).
- UNKNOWN: actual publication wire time; unhashed live HTML.

TIMESTAMP SEMANTICS (kept separate)
- scheduled_release_time: BLS 08:30 ET / FOMC 14:00 ET from calendar + document header
- actual_publication_time: not available
- source timezone: America/New_York
- UTC conversion: ZoneInfo, never fixed EST
- reference_period: survey/meeting month, distinct from release date
- source document vintage: USDL / statement URL + hash
- observed_at_utc: our ingest time (BLS conversions retrieved 2026-09-23; FOMC excerpts ingested 2026-09-28)

DST: US Eastern. 08:30 EDT = 12:30Z; 08:30 EST = 13:30Z; 14:00 EDT = 18:00Z; 14:00 EST = 19:00Z. Tests cover this.

TESTS
-----
`python -m pytest tests/test_macro_official_pit_stage1.py -q` — 7 passed.
Covers: EST vs EDT, FOMC 14:00 EDT vs EST, release vs reference period, first-print overwrite refusal (August NFP +22k vs later -4k), multi-value single event, consensus without asof rejected, source artifact hash stability.
No production tests changed.

OANDA/API REQUESTS:
0
PRODUCTION TRADING LOGIC CHANGED:
NO
V2 POLICY CHANGED:
NO
MODEL TRAINED:
NO
FILES CHANGED:
- reports/decision_quality/_macro_official_pit_stage1.py
- reports/decision_quality/macro_official_pit_stage1.md
- tests/test_macro_official_pit_stage1.py
- data/research/macro/pit_proof/README.md
- data/research/macro/pit_proof/proof_sample.json
- data/research/macro/pit_proof/artifacts/cpi_09112025.official.txt
- data/research/macro/pit_proof/artifacts/cpi_09112025.official.txt.meta.json
- data/research/macro/pit_proof/artifacts/cpi_10242025.official.txt
- data/research/macro/pit_proof/artifacts/cpi_10242025.official.txt.meta.json
- data/research/macro/pit_proof/artifacts/cpi_12182025.official.txt
- data/research/macro/pit_proof/artifacts/cpi_12182025.official.txt.meta.json
- data/research/macro/pit_proof/artifacts/empsit_09052025.official.txt
- data/research/macro/pit_proof/artifacts/empsit_09052025.official.txt.meta.json
- data/research/macro/pit_proof/artifacts/empsit_11202025.official.txt
- data/research/macro/pit_proof/artifacts/empsit_11202025.official.txt.meta.json
- data/research/macro/pit_proof/artifacts/empsit_12162025.official.txt
- data/research/macro/pit_proof/artifacts/empsit_12162025.official.txt.meta.json
- data/research/macro/pit_proof/artifacts/fomc_monetary20250917a.excerpt.txt
- data/research/macro/pit_proof/artifacts/fomc_monetary20251029a.excerpt.txt
- data/research/macro/pit_proof/artifacts/fomc_monetary20251210a.excerpt.txt
STOP.
