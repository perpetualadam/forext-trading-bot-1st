# Quant V2 — Point-in-time consensus sample audit

**Status:** COMPLETE — provenance / vintage audit only. No purchase. No bulk download. No surprise study. No FX join. No model. No production change.

**Returned verdict:**

# PIT_SAMPLE_INCOMPLETE

Experiment D established incremental **magnitude** around official clocks. This task asked whether a defensible **pre-release consensus** series can actually be recovered for those clocks. It cannot be verified from documentation alone, and no legitimate free provider sample was obtainable under the safety rules.

---

## Stage 1 — Frozen PIT acceptance standard

Frozen in `reports/decision_quality/quant_v2_pit_consensus_frozen_sample.json` **before** vendor values were inspected.

For every historical event we would ultimately need:

| Field | Role |
| --- | --- |
| event identity | Stable provider id + match key to Experiment D `event_id` |
| country / currency | USD / GBP / CAD |
| event category | INFLATION / EMPLOYMENT / CENTRAL_BANK_DECISION |
| scheduled release timestamp | Clock, timezone, DST |
| actual publication timestamp | If supplied; not inferred from price |
| units | Percent, thousands, index, bp |
| reference period | Month / quarter the print describes |
| consensus value | Survey / median / mean — semantics named |
| consensus vintage timestamp | When that consensus was known |
| actual first-print | First published number |
| previous-as-known | Previous print known **before** this release |
| revision metadata | Later actual / later previous, separately timestamped |
| provider identity | Source + retrieval + checksum |

**Critical rule:** consensus must be demonstrably pre-release. A current webpage that displays a historical “forecast” column is **not** sufficient.

Acceptable proof: timestamped snapshots, historical API vintages, documented immutable pre-release records, or provider-certified historical consensus snapshots. A historical row returned today with no vintage semantics is **insufficient**.

---

## Stage 2 — Consensus semantics (as documented)

| Term | Econoday (claimed) | Trading Economics (documented schema) | Bloomberg PIT (claimed) |
| --- | --- | --- | --- |
| forecast / consensus | Proprietary panel; **median of ~20 economists**, weekly submissions | `Forecast` = “consensus forecast from a representative group of economists” (**average** stated on calendar/snapshot pages) | Bloomberg survey / ECO consensus |
| TEForecast / model | Not used | Separate **proprietary model**. Not market consensus | Not applicable |
| actual | “Actual-as-released” / initially reported | Schema: **“Latest released value”** | Timestamped actuals + revision history |
| previous | Prior release value | Schema: previous **“after revision if applicable”** | Revision history claimed |
| revised | Initial revision claimed | `Revised` = previous-release value **before** revision | Revision history claimed |
| cutoff / last-update | UNKNOWN | `LastUpdate` = most recent update **or insertion** — not a consensus-asof | Intraday survey-change stream claimed |
| overwritten history | Claims others overwrite; they keep first print | Default calendar vs true as-of snapshot: **UNKNOWN**. Documented PIT page examples use ordinary event-date-range URLs | Dataset sold as PIT |
| contributor count | ~20 claimed | UNKNOWN | Forecaster database claimed large; event-level count UNKNOWN |

UNKNOWN is recorded where docs do not state the fact. `TEForecast` must never be used as consensus.

---

## Stage 3 — Provider shortlist

From the feasibility audit only. No retail-calendar expansion. **Forex Factory is excluded.**

1. **Econoday** — best-documented match to as-known-at-time among calendar vendors.
2. **Trading Economics** — public API schema + claimed PIT product.
3. **Bloomberg Economic Releases and Surveys PIT / ECO** — industry default; enterprise Data License.

Rejected as event-level PIT consensus (already established): official agencies (no consensus), Philadelphia Fed SPF (quarterly), Consensus Economics monthly modules (wrong frequency), OANDA Labs calendar (not vintage-audited; dataset download not authorized here), MQL5, Investing.com / FXStreet scrape.

---

## Stage 4 — Documentation audit

Sources cited: [Econoday enterprise calendar](https://www.econoday.com/enterprise/global-economic-data/), [Econoday API index](https://api.econoday.com/api/api.html), [Econoday 2021 product note](https://www.einpresswire.com/article/484769640/econoday-delivers-live-and-historical-economic-data-to-ai-and-algorithmic-trading-firms), [TE calendar API](https://tradingeconomics.com/api/calendar.aspx), [TE schema](https://docs.tradingeconomics.com/economic_calendar/schema/), [TE PIT page](https://docs.tradingeconomics.com/economic_calendar/point-in-time/), [TE snapshot](https://docs.tradingeconomics.com/economic_calendar/snapshot/), [TE pricing](https://tradingeconomics.com/api/pricing.aspx), [Bloomberg PIT press release](https://www.bloomberg.com/company/press/bloomberg-introduces-point-in-time-economic-data-to-power-quantitative-research-and-strategy-development/).

| Field | Econoday | Trading Economics | Bloomberg PIT |
| --- | --- | --- | --- |
| Historical event coverage | CLAIMED US from 2001; key non-US from 2003 | CLAIMED broad; depth UNKNOWN without key | CLAIMED 3,000+ indicators, 100+ economies, history to 1997 |
| Consensus availability | CLAIMED | CLAIMED (`Forecast`) | CLAIMED |
| Consensus vintage / asof | CLAIMED product thesis; **not verified** on a row | CLAIMED PIT; documented examples are **event-date-range** queries, not a proven as-of vintage | CLAIMED timestamps + intraday survey changes |
| First-print actual | CLAIMED “as initially reported” | Default schema says **latest** actual — **UNSUITABLE** unless a different PIT payload is proven | CLAIMED revision history |
| Revision handling | CLAIMED initial revision kept | `Revised` exists; `Previous` may already be revised | CLAIMED |
| API / export | REST (`geteventsbyrange`, `geteventdetails`, …). Public docs **401 without API code**. Spreadsheet listings claimed | REST JSON/CSV; key required | Data License / Terminal ECO |
| Event identifiers | `uid` / event codes CLAIMED | `CalendarId`, `Ticker`, `Symbol` VERIFIED in docs | Terminal/Data License ids CLAIMED |
| USD / GBP / CAD | CLAIMED US + global including UK; Canada UNKNOWN without listing | CLAIMED country filter includes all three | CLAIMED 100+ economies |
| Licensing | Enterprise / contact sales. Individual MyEconoday products reported discontinued | Account required. Trial **not free** | Enterprise |
| Historical-depth limits | CLAIMED 2001/2003 | UNKNOWN | CLAIMED 1997 |
| Public cost | UNKNOWN | Official trial is paid and auto-renews if not cancelled. Third-party ~$149–$299/mo remains unofficial | UNKNOWN |
| Free sample / demo file | **Not obtained.** “Request a demo” / spreadsheet-on-request. No public research dump | **Not obtained.** Trial fee non-refundable; payment details required — **blocked by safety rules**. `guest:guest` discontinued | **Not obtained.** No public sample |

---

## Stage 5 — Frozen sample (before vendor values)

18 PRIMARY Experiment D events, deterministic chronological first / middle / last inside each stratum. USD first. **Not** chosen by later FX move size.

| ID | Currency | Category | Official clock UTC | Official name |
| --- | --- | --- | --- | --- |
| S01 | USD | INFLATION | 2025-09-11 12:30 | CPI August 2025 |
| S02 | USD | INFLATION | 2026-04-10 12:30 | CPI March 2026 |
| S03 | USD | INFLATION | 2026-08-12 12:30 | CPI July 2026 |
| S04 | USD | EMPLOYMENT | 2025-09-05 12:30 | Employment Situation August 2025 |
| S05 | USD | EMPLOYMENT | 2026-04-03 12:30 | Employment Situation March 2026 |
| S06 | USD | EMPLOYMENT | 2026-08-07 12:30 | Employment Situation July 2026 |
| S07 | USD | FOMC | 2025-09-17 18:00 | FOMC statement |
| S08 | USD | FOMC | 2026-03-18 18:00 | FOMC statement |
| S09 | USD | FOMC | 2026-07-29 18:00 | FOMC statement |
| S10 | GBP | INFLATION | 2025-09-17 06:00 | ONS CPI |
| S11 | GBP | INFLATION | 2026-08-19 06:00 | ONS CPI |
| S12 | GBP | EMPLOYMENT | 2025-09-16 06:00 | ONS labour market |
| S13 | GBP | BoE | 2025-09-18 11:00 | MPC |
| S14 | GBP | BoE | 2026-07-30 11:00 | MPC |
| S15 | CAD | INFLATION | 2025-09-16 12:30 | StatCan CPI |
| S16 | CAD | EMPLOYMENT | 2025-09-05 12:30 | StatCan LFS |
| S17 | CAD | BoC | 2025-09-17 13:45 | BoC rate 09:45 ET |
| S18 | CAD | BoC | 2026-07-15 13:45 | BoC rate 09:45 ET |

Timestamp-stress rows **T01/T02** (BLS lapse-delayed CPI 2025-10-24 and Employment 2025-11-20) are for later vendor-clock checks only. They are **not** consensus-sample events.

---

## Stage 6 — Sample acquisition

**No provider sample was downloaded.**

| Attempt | Result |
| --- | --- |
| Econoday API | `https://api.econoday.com/api/api.html` returns **401 Unauthorized** without a licensed API code |
| Econoday public site | Demo / sales contact only. No free historical consensus file |
| Trading Economics trial | Official pricing: trial **fee is not refundable**; unused trial **auto-charges**. Requires payment details. **Not used** |
| Bloomberg | Data License / Terminal. No public sample |
| Official agencies | Confirm again: **no consensus** |

### Exact sample request to send a vendor (do not send until separately authorized)

Please provide a **research inspection sample** (spreadsheet or API extract) for **only** the 18 frozen events S01–S18, plus clock rows T01–T02 if available, with:

- provider event ID and event name  
- country / currency  
- scheduled timestamp (timezone named)  
- reference period and units  
- consensus / survey value  
- **consensus vintage / last-pre-release timestamp**  
- contributor count and median vs mean  
- actual **first print** and first-print timestamp  
- previous-as-known-before-release  
- any later revised actual / revised previous, separately  
- whether the row is a PIT snapshot or the live latest view  

State in writing that consensus values are the last values known **before** the official scheduled clock, and that first-print actuals are not later revisions.

Preferred first vendor: **Econoday**. Alternate: **Bloomberg PIT**. Trading Economics only if they can show a true as-of snapshot that contradicts the default “latest actual / revised previous” schema.

---

## Stage 7 — Official event matching

Not performed on vendor rows. The frozen sample **is** already matched to Experiment D official clocks. Any later vendor file must match on currency, category, reference period, and scheduled clock (including BoC **09:45 ET**, FOMC **14:00 ET**, BLS **08:30 ET**, ONS **07:00 UK**, BoE **12:00 UK**). Do not force fuzzy matches.

---

## Stage 8 — PIT proof

For every sampled consensus the question remains: **what proves this value existed before release?**

No sampled consensus row was inspected. Classification for S01–S18:

| Provider | Classification |
| --- | --- |
| Econoday | **UNKNOWN** — claims exist; no row vintage seen |
| Trading Economics | **PIT_PLAUSIBLE_NOT_VERIFIED** at product-page level; documented default fields look **NOT_PIT** for actual/previous |
| Bloomberg | **UNKNOWN** — capable in principle; no sample |

A documentation example on TE’s PIT page (2016 US jobless claims) shows `Forecast` and `LastUpdate` but **no consensus-asof distinct from release time**. That example is **not** treated as proof for S01–S18.

---

## Stage 9 — Revision audit

| Provider | Actual semantics | Previous semantics | Leakage risk |
| --- | --- | --- | --- |
| Econoday | CLAIMED first print + initial revision | CLAIMED prior + revisions | UNKNOWN until a sample is diffed against official first prints |
| Trading Economics | Documented **latest** actual | Documented **after revision if applicable** | **HIGH on the default schema** |
| Bloomberg | CLAIMED revision history | CLAIMED | UNKNOWN without sample |

Official first prints (ALFRED / BLS CES vintage / ONS versions / StatCan real-time) remain the clean actuals path. They still do **not** supply consensus.

---

## Stage 10 — Timestamp audit

Lessons from Experiment D that any vendor file must survive:

- BLS 2025 lapse delays (T01/T02): later official clocks are not the original pre-lapse schedule.
- BoC official announcement clock is **09:45 America/Toronto**, not 10:00.
- FOMC statement is **14:00 ET** on the last meeting day; notation votes are not regular decisions.
- DST: 08:30 ET is 12:30 UTC in summer and 13:30 UTC in winter.

Vendor `Date` fields that are date-only or `DateSpan=1` (TE estimated) fail the Experiment D clock standard.

---

## Stage 11 — Cross-source spot check

Official Experiment D clocks are the identity backbone. No vendor actuals were compared to BLS/ONS/StatCan/Fed first prints, because no vendor sample was acquired. When a sample exists, compare **identity and first-print only**. Do not compare FX outcomes.

---

## Stage 12 — Surprise reconstruction feasibility

Causal surprise would be:

`(actual_first_print − consensus_pre_release)` in compatible units, using the official Experiment D clock for market alignment.

| Requirement | Status now |
| --- | --- |
| Actual first print known | Official path **possible**; vendor default TE path **not** |
| Consensus truly pre-release | **Not demonstrated** |
| Units compatible | UNKNOWN until sample |
| Reference period correct | UNKNOWN until sample |
| Revisions separated | TE default **no**; others CLAIMED |
| Reconstruct without hindsight | **No** |

No correlations with FX were computed.

---

## Stage 13 — Coverage (if a licensed file later exists)

| Need | Econoday | TE | Bloomberg |
| --- | --- | --- | --- |
| USD inflation | CLAIMED | CLAIMED | CLAIMED |
| USD employment | CLAIMED | CLAIMED | CLAIMED |
| FOMC | CLAIMED | CLAIMED | CLAIMED |
| GBP inflation / employment / BoE | CLAIMED UK coverage | CLAIMED | CLAIMED |
| CAD inflation / employment / BoC | UNKNOWN without listing | CLAIMED | CLAIMED |

USD should be first. GBP/CAD wait until USD PIT is proven.

---

## Stage 14 — Licensing / cost

- **No purchase made.**
- Econoday: enterprise quote after demo. Public API is keyed. Individual calendar subscriptions reported no longer offered.
- Trading Economics: official trial is a **paid on-ramp** with auto-renew. Third-party June 2026 listings ~$149–$299/month remain unofficial.
- Bloomberg: Data License / Terminal; cost not public.
- Redistribution of calendar compilations is typically contract-restricted. Forex Factory copying remains prohibited.

Do not recommend purchase solely because a product page exists.

---

## Stage 15 — Scorecard

| Category | Econoday | Trading Economics | Bloomberg |
| --- | --- | --- | --- |
| PIT CONSENSUS PROOF | UNKNOWN | UNKNOWN / UNSUITABLE on default schema | UNKNOWN |
| FIRST-PRINT ACTUAL QUALITY | PARTIAL (claimed) | UNSUITABLE (latest actual documented) | PARTIAL (claimed) |
| REVISION SEMANTICS | PARTIAL (claimed) | PARTIAL / leaky previous | PARTIAL (claimed) |
| TIMESTAMP QUALITY | UNKNOWN | PARTIAL (`Date` UTC + `DateSpan`; not D-clock proven) | UNKNOWN |
| EVENT MATCH QUALITY | UNKNOWN | UNKNOWN | UNKNOWN |
| USD COVERAGE | PARTIAL (claimed) | PARTIAL (claimed) | PARTIAL (claimed) |
| GBP COVERAGE | PARTIAL (claimed) | PARTIAL (claimed) | PARTIAL (claimed) |
| CAD COVERAGE | UNKNOWN | PARTIAL (claimed) | PARTIAL (claimed) |
| API/EXPORT PRACTICALITY | PARTIAL (401 without key) | PARTIAL (key + paid trial) | UNKNOWN |
| REPRODUCIBILITY | UNKNOWN | UNKNOWN | UNKNOWN |
| LICENSING/COST | UNKNOWN (enterprise) | PARTIAL (paid trial documented) | UNKNOWN (enterprise) |
| LEAKAGE RISK | UNKNOWN | HIGH on documented default fields | UNKNOWN |

---

## Stage 16 — Minimum later acquisition spec (do not acquire)

If a human later authorizes a **sample**, not a bulk dump:

| Item | Spec |
| --- | --- |
| Provider | One of Econoday or Bloomberg PIT first |
| Events | Frozen S01–S09 only (USD CPI, Employment Situation, FOMC). 9 rows |
| Then, only if those 9 pass E1–E3 | Optional S10–S18 |
| Fields | Stage 1 list, including `consensus_asof_utc ≤ scheduled_ts_utc` |
| Date range | Those 9 clocks only |
| Storage | `data/research/external/raw/<vendor>/<retrieval_date>/` immutable + checksums; never production paths |
| Normalization | New version `pit1`; no overwrite |
| Expected n | 9 USD events |
| Licensing | Written research-inspection permission; no redistribution |

Do **not** acquire it in this task.

---

## Stage 17 — Holdout design

2025-09 through 2026-08 market data is already inspected DEVELOPMENT / DISCOVERY. Joining consensus to it later would **not** create a pristine holdout.

A later surprise experiment, if ever authorized, must:

1. Freeze provider, fields, and cleaning rules on a **sample** first.  
2. Freeze surprise = first-print − last pre-release consensus, units, and alignment to Experiment D clocks.  
3. Treat any study on 2025-09–2026-08 as discovery.  
4. Accumulate a **later chronological** window that is not used to choose the vendor or the surprise definition.  
5. Keep event-level n (not bar n) and Experiment A half-spread as the economic gate.

PIT data does not repair the existing holdout problem.

---

## Stage 18 — Final questions

1. Did any provider demonstrate historical consensus? **Claimed, not demonstrated on a sample.**  
2. Did any provider demonstrate that consensus was truly pre-release? **No.**  
3. Is consensus timestamp/vintage available? **CLAIMED; not verified.**  
4. Are first-print actuals distinguishable from revisions? **Econoday/Bloomberg claim yes. TE default schema says actual is latest.**  
5. Is previous-as-known available? **Not verified. TE previous may be revised.**  
6. Are event timestamps reliable? **Official D clocks yes. Vendor clocks untested. Must re-check lapse dates and BoC 09:45.**  
7. Can official Experiment D events be matched cleanly? **The sample list can. Vendor match is untested.**  
8. Can causal macro surprise be reconstructed? **Not yet.**  
9. Is USD inflation coverage adequate? **CLAIMED. Not verified.**  
10. Is USD employment coverage adequate? **CLAIMED. Not verified.**  
11. Is FOMC coverage adequate? **CLAIMED. Decision-level official; survey expectation untested.**  
12. Are GBP/CAD adequate or should they wait? **Wait until USD PIT is proven.**  
13. What leakage risks remain? Hindsight consensus; TEForecast; latest actual; revised previous; lapse-corrected clocks; date-only vintages; FF scrape.  
14. What would the minimum paid/free acquisition need? The Stage 16 nine-event USD sample with written PIT semantics.  
15. Is a surprise experiment technically justified after this audit? **No.**

---

## Stage 19 — Verdict

# PIT_SAMPLE_INCOMPLETE

Provider claims (especially Econoday actual-as-released + panel median, and Bloomberg’s dated PIT dataset) are **promising enough to request a written sample**. They are **not** proven. Trading Economics’ public default field definitions are a **warning**, not a pass.

This verdict does **not** authorize purchase, subscription, bulk download, or a surprise backtest.

---

## Tests / stop

Focused tests cover the frozen sample list, deterministic selection, official-clock lessons (BoC 09:45, BLS lapse, DST), and the rule that catalog/sample rows carry no consensus/actuals. No vendor sample files were stored.

`python -m pytest -q --tb=line` → **419 passed / 0 failed / 0 skipped / 28.16s**.

No consensus acquired. No actuals purchased. No FX join. No training. No `_quant_stub_vote` change. No filters. No production change. Stop for human review.
