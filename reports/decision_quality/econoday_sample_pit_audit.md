# Econoday sample — point-in-time fundamental data audit

RESEARCH ONLY. Local files from `c:\Users\Brian\Downloads\sample.zip`. No Econoday/OANDA/network calls. No V2 or production changes. No direction tests, no surprise-vs-FX join, no model.

**Final verdict: B** — useful fields exist, but a single static extract does not prove pre-release consensus observability or first-print actuals. The feed’s documented `seq` / last-100-version behaviour is a plausible path to a future PIT pipeline if we archive immutable snapshots ourselves.

---

## 1. Inventory

| File | Format | Purpose |
|---|---|---|
| `Econoday_Standard_Feed_Instructions.pdf` | PDF, Rev **3.05**, dated July 29, 2023 (changelog also lists 3.06) | Authoritative field definitions, ATTRIBUTE bits, delivery, `seq` notes |
| `Macro Event Definitions.xlsx` | Excel, sheet `sheet1`, 1,154 data rows | Catalog of series: `DISPLAY_NAME_ID` × `DISPLAY_VALUE_ID` by country |
| `Macro Sample 2026 Jul-Sep.xml` | XML `EVENTS` / `DATA` / `EVENT` / `VALUES` / `VALUE` | One static feed extract; `DATA date="20260910151035" seq="12"` |

Relationship: the PDF defines the live `feed.xml` / `feed_yr.xml` contract. The Excel lists stable name/value IDs. The XML is one published `DATA` payload covering scheduled releases **2026-07-01 through 2026-09-30**.

Documented live files (not in the ZIP): `feed.xml` (rolling window, refreshed in business hours) and `feed_yr.xml` (current-year snapshot). This ZIP is a dated sample, not a live poll.

### Authoritative identifiers (Econoday terms)

| Term | Meaning (PDF) | Preferred? |
|---|---|---|
| `UID` | Unique for the **event instance** lifetime; does not change if the date moves | **Yes** for a release instance |
| `DISPLAY_NAME_ID` | Immutable ID of the **event name / series** | **Yes** for the series (e.g. Employment Situation) |
| `DISPLAY_VALUE_ID` | Immutable ID of a **value name** on that series | **Yes** for NFP vs unemployment vs AHE |
| `VALUE_UID` | Guaranteed unique ID of **this value instance** | **Yes** for one print of one value |
| `EVENT_CODE` | Legacy immutable event-name code | Deprecated; prefer `DISPLAY_NAME_ID` |
| `EVENT_ID` | Legacy `EVENT_CODE` + `UID` | Deprecated; prefer `UID` |
| `COUNTRY` | Abbreviation (US, GB, JP, AU, CA, CH, EMU, …) | Event-level |
| `NAME` | Event display name (same across releases unless the publisher changes it) | |
| `VALUE_NAME` | Value display name; **not** immutable | Prefer `DISPLAY_VALUE_ID` |
| `RELEASED_FOR` | Period the numbers cover (week / month / quarter) | |
| `RELEASED_ON` | Release date/time, US Eastern | Display |
| `RELEASED_ON_GMT` | Same release clock in GMT | Use this for UTC research |
| `PREVIOUS_DATE` | Previous release date/time (Eastern) | Schedule, not a value |
| `MODIFYDATE` | Last time **Econoday added or modified this event** | Source modify time, not consensus-as-of |
| `DATA@date` | Timestamp the XML file was created (`YYYYMMDDHHMMSS`) | File vintage |
| `DATA@seq` | Feed sequence; increments per unique daily feed | File vintage |
| `ACTUAL` | Numeric print; “usually available at event release time/date” | |
| `CONSENSUS` | Analysts’ expectation; optional | |
| `CONSENSUSRANGEFROM` / `CONSENSUSRANGETO` | Optional range | |
| `PREVIOUS` | **The previous ACTUAL** of the event | Not a separate first-print archive |
| `REVISED` | Appears when revised data is released | |
| `REVISEDHIST` | Documented revision-history amount; **0 rows** in this sample | |
| `CONSENSUSVARIANCE` | `ACTUAL` − `CONSENSUS`; **0 rows** in this sample | |
| `PREFIX` / `SUFFIX` | Display units ($, %, B, …) | |
| `FREQUENCY` | 0 none … 6 annual | |
| `CATEGORY` | Bitfield (1 economic, 2 treasury, 512 central bank, …) | |
| `LISTWEIGHT` | Listing rank; lower = more important | Not the importance bits |
| `ATTRIBUTE` | Bitfield: 1 actual available, 2 consensus available, 4 market mover, 16 non-timed, 64 merit extra attention, 128 revised available, 512 other key indicator, 1024 canceled | |
| `HIGHLIGHTS` | Text after an actual is released | Post-release |
| `CONSENSUSNOTES` | Text after a consensus number is released; **absent** in this XML | |
| `DEFINITION` / `DESCRIPTION` | Not release-specific; **absent** in this XML | |

Page 3 of the PDF loosely says `ACTUAL` is “previous ACTUAL”. Page 8 and the `PREVIOUS` definition contradict that. This audit uses **page 8**: `ACTUAL` is the current print; `PREVIOUS` is the prior `ACTUAL`.

---

## 2. Event universe (from the sample, not from economics textbooks)

XML countries present: US, GB, JP, AU, CA, CH, EMU, DE, FR, IT, NL, BE, FI, plus others (CN, IN, KR, SG, HK, TW, NZ, SE, NO, DK, BR) that are out of scope for the six pairs except as background.

The 2012 country table in the PDF does not list NL/BE/FI; the sample and Excel do. Catalog ≠ 2012 table.

### USD — `COUNTRY=US` (658 events, 2,323 values)

Includes a large Treasury auction/announcement/settlement block. Macro / CB names actually in the XML:

Inflation: CPI, PPI-Final Demand, Import and Export Prices, Atlanta Fed BIE, Farm Prices  
Employment: Employment Situation, ADP Employment Report, Jobless Claims, JOLTS, Challenger, Employment Cost Index  
Activity: GDP, Retail Sales, Durable Goods, Factory Orders, Industrial Production, ISM Mfg/Services, PMI flash/final, Empire/Philly/Dallas/Richmond/KC Fed surveys, Chicago PMI, Business Inventories, Construction Spending, Motor Vehicle Sales  
Housing: Housing Starts and Permits, New/Existing/Pending Home Sales, Case-Shiller, FHFA HPI, Housing Market Index, MBA Mortgage Applications  
Consumer: Consumer Confidence, Consumer Sentiment, Personal Income and Outlays, Consumer Credit, E-Commerce Retail Sales  
Trade / external: International Trade (advance and full), Current Account, TIC  
Labour/productivity: Productivity and Costs  
Central bank: FOMC Announcement, FOMC Meeting Begins, FOMC Minutes, Fed Chair Press Conference, Beige Book, Fed Balance Sheet, many named Fed speeches  
Other: Leading Indicators, NFIB, Corporate Profits, Money Supply, Treasury Statement, energy stock reports

### EUR — several `COUNTRY` codes (do not collapse)

**EMU (47 / 105 values):** HICP, HICP Flash, GDP, GDP Flash, Industrial Production, Retail Sales, Unemployment Rate, PPI, Merchandise Trade, M3, PMI composite/mfg flash & final, EC Consumer Confidence Flash, EC Economic Sentiment, ECB Announcement, ECB Minutes, ECB Lending Survey  

**DE (41 / 99):** CPI, GDP/Flash, Ifo, ZEW, GfK, Industrial Production, Manufacturing Orders, Retail Sales, Unemployment Rate, PPI, Merchandise Trade, PMI flash/final  

**FR (30 / 63):** CPI, GDP/Flash, Industrial Production, ILO Unemployment Rate, Merchandise Trade, Consumer Mfgd Goods Consumption, Business Climate Indicator, PMI, PPI  

**IT (22 / 52):** CPI, GDP, Industrial Production, Retail Sales, Unemployment Rate, Merchandise Trade, PPI, Business and Consumer Confidence  

**NL (28 / 51):** CPI, CPI Flash, GDP, Retail Sales, Labour Force Survey, Manufacturing PMI/Production, Business/Consumer Confidence, Balance of Trade  

**BE (30 / 47):** CPI, HICP, GDP, Retail Sales, Industrial Production, Unemployment Rate, PPI, confidence, Current Account, Balance of Trade  

**FI (32 / 56):** CPI, HICP, GDP/Flash, Industrial Production, Labour Force Survey, PPI, confidence, Current Account, Balance of Trade  

### GBP — `GB` (51 / 127)

CPI, GDP, Monthly GDP, Labour Market Report, Retail Sales, Industrial Production, Merchandise Trade, PPI, PMI flash/final/construction, BoE Announcement & Minutes, BoE Monetary Policy Report, Public Sector Finances, M4, CBI surveys, Nationwide / Lloyds house prices

### JPY — `JP` (31 / 66)

CPI, Tokyo CPI, GDP, Unemployment Rate, Industrial Production, Retail Sales, Household Spending, Merchandise Trade, Machinery Orders, PPI, Bank of Japan Announcement, BoJ Meeting Begins  

Excel also lists Tankan, All Industry Index, Tertiary Index, PMI flash/final that did **not** appear as named events in this Jul–Sep XML window.

### AUD — `AU` (21 / 41)

Monthly CPI, GDP, Labour Force Survey, International Trade in Goods, Capital Expenditures, Wage Price Index, PPI, NAB Business Survey, Westpac-Melbourne consumer sentiment, RBA Announcement, RBA Meeting Minutes  

Excel also lists quarterly CPI, Retail Sales, Goods and Services Trade, Household Spending — not all present as XML events in this quarter.

### CAD — `CA` (32 / 82)

CPI, GDP, Monthly GDP, Labour Force Survey, Retail Sales, Merchandise Trade, Manufacturing Sales, Housing Starts, Industrial Product Price Index, Ivey PMI, Bank of Canada Announcement, BoC Business Outlook Survey, BoC Monetary Policy Report

### CHF — `CH` (27 / 41)

CPI, GDP, GDP Flash, Unemployment Rate, Retail Sales, Merchandise Trade, Producer and Import Price Index, KOF leading indicator, SECO Consumer Climate, SVME PMI, SNB Monetary Policy Assessment  

Excel lists Employment; that name is **not** in this XML window.

---

## 3. Consensus coverage (event vs value)

An EVENT can carry 0–100 VALUE rows. This sample: **844 / 1,294** events have more than one value. Do not treat “Employment Situation” as one number.

| Scope | Events | Values | Events with `CONSENSUS` | Values with `CONSENSUS` | Values with `ACTUAL` | Values with `PREVIOUS` | Values with `REVISED` |
|---|---:|---:|---:|---:|---:|---:|---:|
| Entire XML | 1,294 | 3,658 | 337 (26%) | 603 (16%) | 3,030 | 3,375 | 447 |
| US | 658 | 2,323 | 114 | 200 | 1,978 | 2,102 | 144 |
| EMU | 47 | 105 | 36 | 67 | 85 | 105 | 34 |
| DE | 41 | 99 | 35 | 71 | 88 | 99 | 33 |
| FR | 30 | 63 | 15 | 24 | 55 | 63 | 18 |
| IT | 22 | 52 | 7 | 14 | 44 | 52 | 4 |
| NL | 28 | 51 | **0** | **0** | 37 | 44 | 8 |
| BE | 30 | 47 | **0** | **0** | 31 | 39 | 2 |
| FI | 32 | 56 | **0** | **0** | 43 | 55 | 3 |
| GB | 51 | 127 | 18 | 34 | 94 | 127 | 41 |
| JP | 31 | 66 | 27 | 62 | 50 | 66 | 22 |
| AU | 21 | 41 | 11 | 16 | 36 | 41 | 8 |
| CA | 32 | 82 | 19 | 27 | 67 | 82 | 34 |
| CH | 27 | 41 | 3 | 3 | 33 | 41 | 10 |

`ATTRIBUTE` bit 2 (consensus available) = 337 events, matching events-with-`CONSENSUS`.  
`REVISEDHIST` = 0. `CONSENSUSVARIANCE` = 0. Range tags: 598 values.

Worked multi-value example (US Employment Situation, `DISPLAY_NAME_ID=247`, three monthly prints in the window):

| VALUE_NAME | n | CONSENSUS | ACTUAL | PREVIOUS | REVISED |
|---|---:|---:|---:|---:|---:|
| Nonfarm Payrolls - M/M | 3 | 3 | 3 | 3 | 3 |
| Unemployment Rate | 3 | 3 | 3 | 3 | 0 |
| Private Payrolls - M/M | 3 | 3 | 3 | 3 | 3 |
| Manufacturing Payrolls - M/M | 3 | 3 | 3 | 3 | 3 |
| Average Hourly Earnings - M/M | 3 | 3 | 3 | 3 | 0 |
| Average Hourly Earnings - Y/Y | 3 | 3 | 3 | 3 | 0 |
| Average Workweek | 3 | 3 | 3 | 3 | 0 |
| Participation Rate | 3 | 1 | 3 | 3 | 0 |

Consensus is **per VALUE**, not per EVENT. Participation Rate is not fully covered even on the same release.

Swiss CPI and SNB Assessment have **no `CONSENSUS`** in this extract. NL/BE/FI have actuals but no consensus.

---

## 4. Point-in-time audit

### Timestamp-like fields

| Field | Documented meaning | What it is not |
|---|---|---|
| `RELEASED_ON` / `RELEASED_ON_GMT` | Scheduled/stated **release clock** | Not “when we first saw the actual” |
| `PREVIOUS_DATE` | Prior release clock (Eastern) | Not previous-value vintage |
| `MODIFYDATE` | Last time Econoday **added or modified this event** | Not consensus-as-of; not first-print time |
| `DATA@date` | When **this XML file was created** | Not per-field observability |
| `DATA@seq` | Feed sequence | Not per-field observability |
| `HIGHLIGHTS` | Post-actual commentary | Not a clock |

There is **no** field named consensus-as-of, observed-at, first-print-at, or vintage.

PDF on `CONSENSUS`: optional; “usually available only for the week, released the Friday prior to the current week.” That is a **product habit**, not a per-row timestamp.

### Static CONSENSUS + ACTUAL + MODIFYDATE after release

In this file, **584** values have both `CONSENSUS` and `ACTUAL`. **All 584** also have `MODIFYDATE` **after** `RELEASED_ON_GMT`.

A record that already contains the actual, and was last modified after the release clock, cannot prove that the `CONSENSUS` number sitting next to it is the same number that was visible before release. `MODIFYDATE` only says the event row was touched.

**STATIC SAMPLE DOES NOT PROVE PRE-RELEASE CONSENSUS OBSERVABILITY**

---

## 5. First-print actual

PDF: `ACTUAL` usually appears at release; `REVISED` when revised data is released; `ATTRIBUTE` bit 128 = revised data available (229 events here); `PREVIOUS` = previous `ACTUAL`.

A later feed can overwrite `ACTUAL` and/or fill `REVISED`. One static file cannot tell whether today’s `ACTUAL` is the first print or a later overwrite.

| Question | A) One static sample | B) Successive archived feeds |
|---|---|---|
| First-print `ACTUAL` | **Not proven** | **Possible** if we store the first snapshot that shows `ACTUAL` and never overwrite it |
| Later revision | `REVISED` / bit 128 present, but not a vintage series | **Possible** if we keep every `seq` |
| Revised previous | `PREVIOUS` is just “previous ACTUAL”; no previous-vintage tag | Only if older snapshots still exist |

`REVISEDHIST` is documented and unused in this extract (0 rows).

---

## 6. Safe surprise

Wanted:

`surprise = first_print_actual − last_consensus_observed_before_release`

| Component | Static sample | Successive snapshots |
|---|---|---|
| First-print actual | Not proven | Possible if we archive the first post-release feed that carries `ACTUAL` |
| Last pre-release consensus | Not proven | Possible if we archive a pre-release feed that already has `CONSENSUS` and no `ACTUAL` (19 such values exist even in this mixed file) |

**SAFE SURPRISE FROM STATIC SAMPLE: NO** — **NOT PROVEN from static sample.**

`CONSENSUSVARIANCE` is documented as actual − consensus but is empty here and would inherit the same PIT defect if computed from one mixed row.

Successive immutable snapshots **can** construct a defensible surprise **if** (1) we pull often enough to catch a pre-release consensus row and a first actual row, (2) we never overwrite, (3) we treat `MODIFYDATE` as source hygiene only, not as as-of.

---

## 7. Snapshot collection design (DESIGN — not implemented)

Documented feed behaviour to hang a collector on:

- `feed.xml` refreshed through the business day when new data is published  
- May update on the weekend when consensus is released  
- Daily feeds carry incrementing `seq`; last **100** versions remain as `feed.xml-N`  
- Never overwrite our store; treat each pull as a new object  

Proposed row (research store, future):

| Field | Source |
|---|---|
| `source` | `econoday` |
| `schema_version` | PDF revision (3.05 / 3.06) + feed type (`feed` / `feed_yr` / sample) |
| `feed_seq` | `DATA@seq` |
| `feed_created` | `DATA@date` (source file time) |
| `observed_at_utc` | **our** pull clock |
| `raw_snapshot_hash` | hash of the XML bytes we received |
| `uid` | event instance |
| `display_name_id` / `name` / `event_code` | series |
| `country` | `COUNTRY` |
| `value_uid` / `display_value_id` / `value_name` | value series |
| `released_for` | period |
| `released_on_gmt` | scheduled/stated release |
| `actual` / `consensus` / `previous` / `revised` / ranges | VALUE tags as present (nullable) |
| `source_modify_time` | `MODIFYDATE` |
| `attribute` / `listweight` / `frequency` / `category` | event bits |

**SOURCE TIMESTAMP** = `DATA@date`, `MODIFYDATE`, `RELEASED_ON_GMT`.  
**OUR OBSERVED-AT TIMESTAMP** = `observed_at_utc` only.  
These must never be collapsed.

---

## 8. Consensus snapshot schedule

**Documented (PDF):** consensus is usually a weekly figure, released the Friday before the current week; the file may update on the weekend when consensus is available; the file also refreshes through business days.

**Not documented:** intra-week consensus revisions, tick-level changes, or a guaranteed last-print-before-release API.

**DESIGN (not claimed as Econoday behaviour):**

1. Weekend / Friday pull after the documented consensus refresh  
2. Daily pre-release pulls for events in T−5d … T−0  
3. A pull in the hour before `RELEASED_ON_GMT` when timed  
4. Pulls just after release until `ACTUAL` appears  
5. Later pulls for `REVISED`  

Targets: early consensus, later consensus, last observable pre-release consensus, first observable actual. Label each with `observed_at_utc`.

---

## 9. Event-time feature design (not implemented)

Join grain must be **`UID` + `DISPLAY_VALUE_ID`**, then map countries to pairs. Never attach post-release fields to a V2 observation whose `timestamp_utc` is before `RELEASED_ON_GMT`.

**PRE-RELEASE (only if a snapshot with `observed_at_utc` < `RELEASED_ON_GMT` exists):**

- `minutes_to_event` from `RELEASED_ON_GMT`  
- `country`, `display_name_id`, `name`, `value_name` / `display_value_id`  
- `category` / `attribute` importance bits / `listweight`  
- `released_for`, `frequency`  
- `consensus`, `consensus_range_*`, `previous` **as they stood on that snapshot**  
- `consensus_change` only as difference between **two pre-release snapshots**  
- event clustering: count of other timed releases in ±N minutes (schedule only)

**POST-RELEASE ONLY** (`observed_at_utc` ≥ release, or tags that the PDF says appear after the print):

- `actual`  
- `revised` / `revisedhist`  
- `consensusvariance`  
- `highlights`  
- surprise / standardized surprise (only after both PIT legs exist)  
- revision vs first stored actual  

`HIGHLIGHTS` is explicitly post-actual. `CONSENSUSNOTES` is post-consensus-publication, still not a substitute for as-of time.

---

## 10. Multi-currency mapping (no BUY/SELL)

| Econoday `COUNTRY` | Candidate pairs | Notes |
|---|---|---|
| US | All six USD crosses | Do not pick a direction |
| GB | GBP_USD | |
| JP | USD_JPY | |
| AU | AUD_USD | |
| CA | USD_CAD | |
| CH | USD_CHF | |
| EMU | EUR_USD, and possibly other USD crosses via EUR | Euro-area aggregate |
| DE, FR, IT, NL, BE, FI | Ambiguous | Member-state prints. May matter for EUR_USD; may not. Do **not** auto-map every NL CPI Flash to EUR_USD without a written rule |
| ALL | Ambiguous | Global PMI / IPO rows in Excel |

Speeches and untimed events (`ATTRIBUTE` bit 16, 130 events) have weak clocks; do not treat `RELEASED_ON_GMT` midnight as a hard event time without checking that bit.

---

## 11. Sample statistics

| Item | Value |
|---|---|
| Sample file vintage | `DATA date=20260910151035`, `seq=12` |
| Release-clock coverage | 2026-07-01 … 2026-09-30 UTC |
| `MODIFYDATE` span | 2024-08-09 … 2026-09-10 (Eastern) |
| Excel catalog rows | 1,154 value-series definitions |
| Total XML events | **1,294** |
| Total XML value rows | **3,658** |
| Events with consensus | **337** (26%) |
| Values with consensus | **603** (16%) |
| Values with consensus and actual | 584 |
| Values with consensus and no actual | 19 |
| Values with actual and no consensus | 2,446 |
| Multi-value events | 844 |

Relevant-economy XML counts are in §3. Excel series counts (unique event **names** in the catalog): US 115, GB 19, JP 19, AU 15, CA 12, CH 12, EMU 20, DE 18, FR 12, IT 8, NL 11, BE 11, FI 11.

---

## 12. V2 compatibility (no V2 edits)

Existing slots: `macro_event_id`, `macro_event_type`, `official_release_time_utc`, `consensus_value`, `consensus_provider`, `consensus_asof_utc`, `actual_first_print`, `surprise_raw`, `surprise_standardized`, `consensus_revision`, `news_sentiment`, `market_implied_expectation`, `external_data_provenance`, `external_data_available`.

| Econoday field | Potential V2 field | PIT-safe from this static sample? | Conditions |
|---|---|---|---|
| `UID` | `macro_event_id` | ID only, yes | Instance key; not a value |
| `DISPLAY_NAME_ID` / `NAME` | `macro_event_type` | Label only | Prefer ID; many values per name |
| `RELEASED_ON_GMT` | `official_release_time_utc` | Schedule clock, yes | Check `ATTRIBUTE` non-timed |
| `CONSENSUS` | `consensus_value` | **NO** | Need pre-release snapshot |
| (none) | `consensus_asof_utc` | **NO field in feed** | Must be **our** `observed_at_utc` |
| literal `"econoday"` | `consensus_provider` | Yes | |
| `ACTUAL` | `actual_first_print` | **NO** as first-print | Need first post-release snapshot |
| `CONSENSUSVARIANCE` | `surprise_raw` | **NO** | Empty here; same PIT defect |
| (compute) | `surprise_standardized` | **NO** | Needs a PIT panel and a scale |
| `REVISED` | not a clean map; not `consensus_revision` | Partial | Revision of actual, not of consensus |
| `MODIFYDATE` | provenance `publication_time` / source modify | Yes as source hygiene | Not as-of |
| `DATA@date` / `seq` / hash | `external_data_provenance` | Yes | Snapshot identity |
| `COUNTRY` | **missing** in V2 slots | n/a | Required for pair mapping |
| `DISPLAY_VALUE_ID` / `VALUE_UID` / `VALUE_NAME` | **missing** | n/a | Multi-value grain |
| `PREVIOUS` | **missing** | Not PIT | Prior actual only |
| `RELEASED_FOR` | **missing** | Period label | |
| `ATTRIBUTE` / `LISTWEIGHT` | **missing** | Importance / status | |
| `CONSENSUSRANGE*` | **missing** | Optional | |
| `HIGHLIGHTS` | not `news_sentiment` | Post-release text | Do not stuff into sentiment |
| (none) | `market_implied_expectation` | Absent | |

Missing V2 concepts if Econoday is used later: country, value-level IDs, previous, revised, period, importance bits, explicit `source_modify_time` vs `observed_at_utc`, snapshot `seq`/hash.

---

## 13. Performance

Not computed. No join to V2 outcomes. No hit rate, R, profit factor, or 65% claim.

---

## Verdict

The schema is a real event/value calendar with consensus, actual, previous, revised, a release clock, and a feed `seq`. That is enough to **design** an immutable collector.

This ZIP is one mixed post-release file. It does not prove pre-release consensus or first-print actuals. NL/BE/FI and Swiss CPI/SNB show that consensus is not universal even among relevant economies.

**B — useful fields exist but PIT provenance is insufficient** until successive `feed.xml` versions are archived under a split source-time vs observed-at key.
