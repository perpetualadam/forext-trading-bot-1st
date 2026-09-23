# Official 2025 BLS first-print CPI and Employment Situation dataset

**Status:** STAGE 1 COMPLETE — research only. No consensus. No surprise. No FX backtest. No production change.

Calendar window: scheduled release dates `2025-01-01` through `2025-12-31`.

Normalized output: `data/research/macro_first_print/normalized/events_2025.csv` (and `.json`).

---

## EXISTING CODE AUDIT

Inspected `forex_bot/decision_quality/`, `data/research/`, and `reports/decision_quality/` before adding this package.

Already present and reused:

| Existing piece | What it is | Reuse |
| --- | --- | --- |
| `schedule.py` `local_clock_to_utc` | DST-aware `America/New_York` wall clock to naive UTC | Scheduled 08:30 ET conversion. Do not hard-code 13:30 UTC. |
| `schedule.parse_bls_year_lines` | Official BLS year-page line parser | 2025 CPI / Employment catalog clocks |
| `schedule.BLS_RESCHEDULED_UTC` | 2025 lapse-delayed clocks | Flag `official_2025_lapse_delay` |
| `data/research/external/raw/BLS/2026-09-19/year_2025_cpi_empsit.txt` | Experiment D copy of https://www.bls.gov/schedule/2025/ | Primary 2025 schedule evidence |
| `data/research/external/normalized/official_schedule_events_d1.json` | Experiment D official clocks, **no actuals** | Clocks only; not first-print values |
| Experiment D acquire headers / 1.2s pacing | Official-page GET style | Same UA/pacing for direct BLS GETs |
| `quant_v2_external_information_feasibility.md` | ALFRED/FRED vintage limits | ALFRED is date-only, secondary |
| `trading_economics/` pretrial harness | Commercial calendar, unused here | Not used. Stage 2 may revisit consensus separately. |
| `isolation.py` rglob | Broker-isolation over subpackages | New package is scanned |

Not present before this stage (and therefore newly built):

- No archived BLS news-release first-print store
- No CPI/NFP actuals in Experiment D
- No first-print vs revision split
- No ALFRED vintage pull (still not pulled)

FOMC clocks exist in Experiment D. They are out of Stage 1 scope.

---

## SOURCE METHODOLOGY

1. Build the 2025 event catalog from the official BLS year schedule already stored by Experiment D.
2. Map each scheduled date to the official archive URL `https://www.bls.gov/news.release/archives/{cpi\|empsit}_MMDDYYYY.htm`.
3. Retrieve the historical news release itself. The release text is the only source of first-print values.
4. Parse lead sentences (and Table A only as a cross-check for CPI).
5. Attach the official 08:30 ET schedule clock with DST-aware UTC.
6. Leave missing fields missing. Do not fill from today's BLS or FRED series.

Direct `requests` / `curl` GETs to `bls.gov` on 2026-09-23 returned Akamai **403 Access Denied** (bot policy). Those 403 bodies are kept under `raw/bls/{cpi,employment}/*.htm` with `http_status=403` and are **not** parsed as releases.

Official archive HTML was then retrieved through the Cursor official-page gateway and stored as converted text (`*.official.txt`) with the official source URL, retrieval timestamp, SHA256, and content-type `text/plain; converted-from-official-bls-html`. That converted official-page text is what the parsers read.

2025 TXT archives are not offered on the official BLS archive indexes (TXT stops in the mid-2000s). 2025 official archive indexes list **PDF**. HTML archive URLs still resolve and contain the same news-release lead text.

---

## OFFICIAL SOURCES USED

- https://www.bls.gov/schedule/2025/ — 2025 release schedule (Experiment D copy)
- https://www.bls.gov/bls/news-release/cpi.htm — CPI archive index (October 2025 officially unpublished)
- https://www.bls.gov/bls/news-release/empsit.htm — Employment archive index (October 2025 officially unpublished)
- https://www.bls.gov/news.release/archives/cpi_MMDDYYYY.htm — 11 CPI HTML archives with scheduled dates in 2025
- https://www.bls.gov/news.release/archives/empsit_MMDDYYYY.htm — 11 Employment HTML archives with scheduled dates in 2025

Not used: Trading Economics, Bloomberg, Econoday, current BLS time-series API, current FRED observations, ALFRED vintages.

---

## CPI EXTRACTION METHOD

From the archived release text:

- Headline MoM: CPI-U seasonally adjusted monthly change in the lead (`increased` / `decreased` / `was unchanged`)
- Headline YoY: "Over the last 12 months, the all items index ..."
- Core MoM / YoY: "all items less food and energy" lead sentences
- Previous as-known: "after rising/falling X percent" when that clause is in the same release
- Table A (`All items` / `All items less food and energy`) is a cross-check only, scoped to the Table A block so later index-level tables cannot overwrite it
- USDL number and embargo line
- If the lead states a **2-month** seasonally adjusted change, MoM first-print stays missing and the row is `AMBIGUOUS`

---

## EMPLOYMENT EXTRACTION METHOD

From the archived release text:

- NFP first print: "Total nonfarm payroll employment" plus `by N` or parenthetical `(+N)`
- Unemployment rate: first singular "unemployment rate ... X percent"
- AHE MoM / YoY from the all-employees private nonfarm sentence
- Participation rate when stated
- Previous payroll as presented / prior-month revision / two-month net revision from the standard CES revision paragraph
- Two-month revision is stored only when that revision paragraph also parsed, so benchmark asides cannot stand in for it

The January 2025 first print remains `+143,000` even though later releases present a revised January value.

---

## TIMEZONE METHOD

Official local clock is **08:30 America/New_York** from the BLS schedule.

Conversion: `schedule.local_clock_to_utc` (`ZoneInfo("America/New_York")` → UTC).

Examples in this dataset:

| Release | Local | UTC |
| --- | --- | --- |
| 2025-01-10 Employment (EST) | 2025-01-10T08:30:00 | 2025-01-10T13:30:00Z |
| 2025-07-03 Employment (EDT) | 2025-07-03T08:30:00 | 2025-07-03T12:30:00Z |
| 2025-10-24 CPI (EDT, lapse delay) | 2025-10-24T08:30:00 | 2025-10-24T12:30:00Z |
| 2025-12-16 Employment (EST, lapse delay) | 2025-12-16T08:30:00 | 2025-12-16T13:30:00Z |

`08:30 ET = 13:30 UTC` is not assumed year-round.

The news-release embargo line is the scheduled embargo, not an independently measured wire time. `actual_release_time` is therefore **not** manufactured.

---

## FIRST-PRINT DEFINITION

A value is `VERIFIED_FIRST_PRINT` only when the historical official release itself states it.

- CPI: headline MoM, headline YoY, core MoM, and core YoY all established by that release (lead, with Table A agreement when Table A is present)
- Employment: NFP change and unemployment rate established, plus at least one of AHE MoM / AHE YoY / participation
- `PARTIAL`: some required fields missing
- `AMBIGUOUS`: internal conflict, or the release does not state a standard monthly first print
- `FAILED`: no official release text

Matching today's BLS/FRED database is **not** a verification reason.

---

## REVISION HANDLING

First-print fields live on the event that announced them and are never overwritten.

Example in this file:

- January 2025 Employment first print: `nfp_first_print = 143000` (release 2025-02-07)
- March 2025 release presents January as `+125,000` (`previous_nfp_as_presented = 125000`, `previous_nfp_revision = -18000`)

`first_prints_immutable` is empty on the 2025 set: no later revised previous value was written onto an earlier first print.

---

## ALFRED/FRED VALIDATION

ALFRED/FRED was **not** called.

Secondary only, later:

- `UNRATE` first-release vintages may check the printed unemployment rate (vintage **date**, not 08:30 clock)
- `CPIAUCSL` / `CPILFESL` first-release values are **index levels**, not the printed MoM/YoY percents
- `PAYEMS` is an employment **level**, not the printed monthly NFP change

ALFRED cannot replace a missing archived BLS news release. Current FRED observations were not used as first prints.

---

## CPI AUDIT TABLE

| Release date | Reference month | Release UTC | Headline MoM | Headline YoY | Core MoM | Core YoY | Validation |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 2025-01-15 | 2024-12 | 2025-01-15T13:30:00Z | 0.4 | 2.9 | 0.2 | 3.2 | VERIFIED_FIRST_PRINT |
| 2025-02-12 | 2025-01 | 2025-02-12T13:30:00Z | 0.5 | 3.0 | 0.4 | 3.3 | VERIFIED_FIRST_PRINT |
| 2025-03-12 | 2025-02 | 2025-03-12T12:30:00Z | 0.2 | 2.8 | 0.2 | 3.1 | VERIFIED_FIRST_PRINT |
| 2025-04-10 | 2025-03 | 2025-04-10T12:30:00Z | -0.1 | 2.4 | 0.1 | 2.8 | VERIFIED_FIRST_PRINT |
| 2025-05-13 | 2025-04 | 2025-05-13T12:30:00Z | 0.2 | 2.3 | 0.2 | 2.8 | VERIFIED_FIRST_PRINT |
| 2025-06-11 | 2025-05 | 2025-06-11T12:30:00Z | 0.1 | 2.4 | 0.1 | 2.8 | VERIFIED_FIRST_PRINT |
| 2025-07-15 | 2025-06 | 2025-07-15T12:30:00Z | 0.3 | 2.7 | 0.2 | 2.9 | VERIFIED_FIRST_PRINT |
| 2025-08-12 | 2025-07 | 2025-08-12T12:30:00Z | 0.2 | 2.7 | 0.3 | 3.1 | VERIFIED_FIRST_PRINT |
| 2025-09-11 | 2025-08 | 2025-09-11T12:30:00Z | 0.4 | 2.9 | 0.3 | 3.1 | VERIFIED_FIRST_PRINT |
| 2025-10-24 | 2025-09 | 2025-10-24T12:30:00Z | 0.3 | 3.0 | 0.2 | 3.0 | VERIFIED_FIRST_PRINT |
| 2025-12-18 | 2025-11 | 2025-12-18T13:30:00Z |  | 2.7 |  | 2.6 | AMBIGUOUS |

October 2025 CPI: officially unpublished (lapse). No row.

---

## EMPLOYMENT AUDIT TABLE

| Release date | Reference month | Release UTC | NFP first print | Unemployment | AHE MoM | Previous payroll as presented | Revision | Validation |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2025-01-10 | 2024-12 | 2025-01-10T13:30:00Z | 256000 | 4.1 | 0.3 | 212000 | -15000 | VERIFIED_FIRST_PRINT |
| 2025-02-07 | 2025-01 | 2025-02-07T13:30:00Z | 143000 | 4.0 | 0.5 | 307000 | 51000 | VERIFIED_FIRST_PRINT |
| 2025-03-07 | 2025-02 | 2025-03-07T13:30:00Z | 151000 | 4.1 | 0.3 | 125000 | -18000 | VERIFIED_FIRST_PRINT |
| 2025-04-04 | 2025-03 | 2025-04-04T12:30:00Z | 228000 | 4.2 | 0.3 | 117000 | -34000 | VERIFIED_FIRST_PRINT |
| 2025-05-02 | 2025-04 | 2025-05-02T12:30:00Z | 177000 | 4.2 | 0.2 | 185000 | -43000 | VERIFIED_FIRST_PRINT |
| 2025-06-06 | 2025-05 | 2025-06-06T12:30:00Z | 139000 | 4.2 | 0.4 | 147000 | -30000 | VERIFIED_FIRST_PRINT |
| 2025-07-03 | 2025-06 | 2025-07-03T12:30:00Z | 147000 | 4.1 | 0.2 | 144000 | 5000 | VERIFIED_FIRST_PRINT |
| 2025-08-01 | 2025-07 | 2025-08-01T12:30:00Z | 73000 | 4.2 | 0.3 | 14000 | -133000 | VERIFIED_FIRST_PRINT |
| 2025-09-05 | 2025-08 | 2025-09-05T12:30:00Z | 22000 | 4.3 | 0.3 | 79000 | 6000 | VERIFIED_FIRST_PRINT |
| 2025-11-20 | 2025-09 | 2025-11-20T13:30:00Z | 119000 | 4.4 | 0.2 | -4000 | -26000 | VERIFIED_FIRST_PRINT |
| 2025-12-16 | 2025-11 | 2025-12-16T13:30:00Z | 64000 | 4.6 |  | 108000 | -11000 | VERIFIED_FIRST_PRINT |

October 2025 Employment Situation: officially unpublished (lapse). No row.

The 2025-08-01 row is the large CES revision print (`previous` June as presented `+14,000`, two-month net `-258,000`). June's original first print on 2025-07-03 remains `+147,000`.

---

## MISSING / AMBIGUOUS RECORDS

- **October 2025 CPI and Employment:** official non-publication. Quality-check gap, not a manufactured print.
- **November 2025 CPI (released 2025-12-18):** BLS published a seasonally adjusted **2-month** change from September to November because October was not collected. Headline/core MoM first prints left missing. YoY 2.7 / core YoY 2.6 are in the release. Status `AMBIGUOUS`.
- Some Employment AHE YoY / two-month revision cells are empty when that release did not state them in the parsed sentences. Missing stays missing.
- December 2025 reference-month prints (released January 2026) are outside this window.

---

## QUALITY CHECK RESULTS

- Duplicate release dates: none
- Duplicate reference periods: none
- Official unpublished October gaps: recorded for both series
- Timezone conversions: EST 13:30Z / EDT 12:30Z checked
- Publication date vs official schedule date: aligned
- Source hash identity: 403 HTML and later official text are different files; originals not overwritten
- Revision overwrite: `first_prints_immutable` = `[]`
- Impossible percentages / malformed payrolls: none
- Missing required first-print values: only `CPI_2025-11_2025-12-18` (intentional 2-month case)

---

## TEST RESULTS

`python -m pytest tests/test_macro_first_print.py -q` — **14 passed**. Network not required.

Covered: historical lead/HTML parsing, first-print immutability, revised previous does not overwrite, CPI percent parsing, NFP integer parsing, negative payroll, EST and EDT conversion, catalog 11+11, duplicate detection, missing/malformed fields, provenance/hash no-overwrite, two-month CPI not treated as MoM, parenthetical / edged NFP, no production imports.

---

## KNOWN LIMITATIONS

- Raw official **HTML bytes** were not stored; Akamai blocked direct scripted GETs. Preserved evidence is (a) the 403 bodies and (b) converted official archive-page text with URL + SHA256.
- No independently measured actual release time (only the official 08:30 ET embargo/schedule).
- ALFRED vintage cross-check was not run.
- November 2025 CPI has no standard MoM first print in the historical release.
- Parser coverage is 2025 BLS wording. Other years will need a fixture pass before extension.
- Official PDFs exist on the archive indexes and were not stored as binary PDFs in this stage.

---

## NEXT STEP

Manual spot-check of this 2025 file.

Stage 2 (separate): genuinely pre-release historical consensus. Do not compute surprise or backtest FX until that consensus investigation is done.

Do not extend the year range, scrape commercial calendars, or wire this into live signals.

---

## FINAL VERDICT

EXPECTED CPI RELEASES: 11 published (official 2025 cadence minus October 2025 unpublished)
FOUND CPI RELEASES: 11
VERIFIED CPI FIRST-PRINT EVENTS: 10
AMBIGUOUS CPI EVENTS: 1
EXPECTED EMPLOYMENT RELEASES: 11 published (official 2025 cadence minus October 2025 unpublished)
FOUND EMPLOYMENT RELEASES: 11
VERIFIED EMPLOYMENT FIRST-PRINT EVENTS: 11
AMBIGUOUS EMPLOYMENT EVENTS: 0
FIRST-PRINT VALUES TAKEN FROM CURRENT REVISED SERIES: NO
HISTORICAL BLS RELEASES PRESERVED: YES
FX DATA MODIFIED: NO
PRODUCTION CODE CHANGED: NO
LIVE STRATEGY CHANGED: NO
OANDA ORDERS SENT: NO
DOCKER RESTARTED: NO
