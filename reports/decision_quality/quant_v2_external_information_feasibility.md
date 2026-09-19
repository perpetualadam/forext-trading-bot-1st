# Quant V2 — External Information Feasibility / Vintage Audit

**Status:** COMPLETE — research planning only. No external data downloaded. No model. No production change.

**Question this task is allowed to answer:** can genuinely new external information be obtained **historically, causally, reproducibly, and with correct publication vintages**?

**Question this task is not allowed to answer:** does any external series predict FX direction or clear G3?

**Parents:** V1 **NO ECONOMICALLY USEFUL EVENT FOUND**. A **A_USEFUL_CONTEXT_BUT_BELOW_G3**. B **B_USEFUL_CONTEXT_BUT_BELOW_G3**. C **C_RESOLVES_PATH_BUT_BELOW_G3**.

**Established internal-market-data fact carried forward:** no tested MID / spread / activity / residual / dispersion / M1-path relationship passed G3. The remaining V2 branches that are not a re-cut of these prices are calendar, macro, and rates.

---

## Verdict

# EXTERNAL_DATA_FEASIBILITY_INCOMPLETE

Defensible **official actuals** and **official scheduled-event metadata** exist for several required currencies. Defensible **pre-release consensus** does **not** exist in this repository, is **not** provided by official agencies, and has **not** been independently vintage-audited from any vendor. A surprise study is therefore **not** authorized. Paid purchase is **not** authorized. Scraping is **not** authorized.

This is not `EXTERNAL_DATA_NOT_JUSTIFIED`: official schedule/actual sources are real and, for a **proximity / magnitude** experiment, conceptually researchable. It is not `EXTERNAL_DATA_ACQUISITION_JUSTIFIED`: remaining UNKNOWNs on consensus vintage, multi-currency clock-time archives, licensing, and cost are material. Acquisition waits for human review and the E1–E6 gates below.

---

## Stage 1 — Repository inventory

Search covered `forex_bot/`, `tests/`, `data/`, `reports/decision_quality/`, `requirements.txt`, `.env.example`, and V1/V2 research notes. Production was not modified.

| Class | Status | Evidence |
| --- | --- | --- |
| Economic calendar code | **ABSENT** | No calendar module, downloader, or join. `oandapyV20.endpoints.forexlabs.Calendar` exists only as a **dependency class**. This repo never calls it. |
| Macro data | **ABSENT** | No CPI/NFP/GDP/PMI tables or files. |
| News data | **ABSENT** | Live API-voter payload audit already recorded **no news**. No news cache. |
| Rate / yield data | **ABSENT** | No policy-rate, OIS, or Treasury files. |
| Event schemas | **PARTIAL** | V2 research plan Stage 9 wrote a **documentation-only** causal schema. No implemented table. |
| API integrations | **PARTIAL** | OANDA candles/account/orders; optional LLM / Telegram / Discord. No calendar, FRED, Econoday, or news API. |
| Unused environment variables for external info | **ABSENT** | `.env.example` has no `CALENDAR_*`, `FRED_*`, `NEWS_*`, `MACRO_*`, or yield keys. Unused knobs that exist are bot/risk/session, not external data. |
| Dependencies | **ABSENT** for external info | `requirements.txt`: dotenv, pandas, numpy, requests, psycopg2, fastapi, uvicorn, oandapyV20, tzdata. No FRED, Trading Economics, news, or SDMX client. |
| Historical caches | **ABSENT** for external info | On disk: six M5 CSVs, six M1 CSVs under `data/historical/m1/`, `data/eurusd_m5_2024_sample.csv`, `data/research/quant_features/six_pair_features.pkl`. |
| False friends | **Not a calendar** | `session_rules.py` uses timezone calendars (BST/GMT). `backtest.py` `REGIME_PERIODS` are **hand-curated year windows** (euro crisis, Brexit, COVID, …), not timestamped releases. `tests/test_consensus_truth_table.py` is **ensemble voting**, not economist consensus. |

V2 plan Stage 5 already recorded: no calendar / rates / order-book files. That inventory still holds after A/B/C.

---

## Stage 2 — Causal data requirements

Frozen **before** any provider recommendation. A scheduled macro release, if later collected, must be stored with these fields.

### Required fields

| Field | Meaning |
| --- | --- |
| `event_id` | Stable research identifier (not a vendor-only ephemeral row id, though vendor ids may be kept as aliases) |
| `research_category` | One of the Stage 5 taxonomy values |
| `provider_label` | Provider’s original event name |
| `currency` | ISO currency most directly affected (`USD`, `EUR`, …) |
| `country` / `economy` | Publishing economy |
| `event_category_raw` | Provider category string |
| `scheduled_ts_utc` | Scheduled release instant, normalized to UTC |
| `scheduled_tz_source` | Timezone the schedule was published in (e.g. America/New_York, Europe/London) |
| `scheduled_precision` | `clock` / `date_only` / `estimated` |
| `importance_asof` | Importance **as known before the event**, if any |
| `consensus_forecast` | Pre-release survey value, or null |
| `consensus_asof_utc` | Last timestamp at which that consensus was known |
| `consensus_source` | Survey vendor; never “official agency” unless the agency itself publishes a survey |
| `previous_as_known` | Previous print **known before this release** |
| `actual_first` | First published actual |
| `actual_publication_ts_utc` | Instant the actual became public |
| `revision_*` | Later values with their own timestamps |
| `units` | Percent, thousands, index, … |
| `source_agency` | BLS, ONS, Eurostat, … |
| `retrieval_ts_utc` | When **we** fetched the row |
| `vintage_id` | Provider vintage / point-in-time key |
| `row_status` | `KNOWN_BEFORE` / `AT_RELEASE` / `LATER_ONLY` applicability of each payload |

### When a field may be used

| Bucket | Fields | Allowed use |
| --- | --- | --- |
| **KNOWN BEFORE EVENT** | `event_id`, category, currency, `scheduled_ts_utc`, pre-release importance, `consensus_forecast` **only if** `consensus_asof_utc ≤ scheduled_ts_utc` (and preferably ≤ first eligible market bar), `previous_as_known` | Pre-event filters, proximity, magnitude-around-schedule hypotheses |
| **AVAILABLE AT RELEASE** | `actual_first`, `actual_publication_ts_utc`, surprise = actual − consensus **only if** consensus was already in the before-event bucket | Post-release direction / surprise hypotheses. First eligible market bar is **after** `actual_publication_ts_utc` |
| **AVAILABLE ONLY LATER** | Revisions, restated previous, later importance re-ratings, “final” consensus, corrected timestamps | Diagnostics and vintage audit. **Never** as a live feature or as the historical surprise |

If `actual_publication_ts_utc` is missing, the actual **must not** be joined to market bars using only the scheduled clock. Date-only vintages (typical of ALFRED) are **not** M5-safe publication timestamps.

---

## Stage 3 — Vintage / revision requirements

### Leakage hazards (predeclared)

1. Using the **revised** actual as if it were the first print.
2. Using today’s consensus as if it existed last year.
3. Using a consensus that the vendor **overwrote** after the print.
4. Using a **corrected** event timestamp that was not the time the market saw.
5. Using a **revised previous** that was not known before the event.
6. Using **future** importance classifications (a “high-impact” tag assigned after a large move).
7. Using the latest macro database (FRED-today, Eurostat-today) as the historical release.
8. Inferring event times from later realized volatility (outcome leakage).
9. Aligning an actual to an M5/M1 bar whose **start** is before the actual was public.
10. Treating ALFRED `realtime_start` **dates** as 00:00 UTC clock times.
11. Treating daily policy-rate / yield observations as intra-day decision timestamps.
12. Building surprise from official actuals minus a **hindsight** forecast (TEForecast model, ARIMA, or our own fit on later data).

### AS-KNOWN-AT-TIME standard

A field is usable at research time *T* only if a **stored vintage** shows that field’s value, and its validity interval, with `valid_from ≤ T < valid_to` (or open-ended `valid_to` only for the current live vintage). For post-release labels, *T* is `actual_publication_ts_utc`. For pre-event features, *T* is the **first eligible completed market bar start**, which is strictly after the information is known (Stage 12).

Any provider that returns only the latest snapshot, or that cannot show first-release vs later revision, is **incapable of satisfying this standard** for surprise or first-print studies. It may still be usable for **scheduled-time proximity** if the **schedule itself** is historically dated.

---

## Stage 4 — Currency coverage

Required currencies and logically relevant official economies. **No predictive claim.**

| Currency | Economy / issuer | Central bank | Logically relevant external classes |
| --- | --- | --- | --- |
| USD | United States | Federal Reserve (FOMC) | US inflation, employment, growth, surveys, retail, FOMC decision/communication, US policy rate, US Treasury / money-market yields |
| EUR | Euro area | ECB | EA inflation (HICP), employment, growth, surveys (PMI/ESI), ECB decision/communication, ECB policy rates, German/OA yields as **slow context** |
| GBP | United Kingdom | Bank of England (MPC) | UK CPI, labour, GDP, surveys, MPC decision/minutes/report, Bank Rate, gilt / SONIA context |
| JPY | Japan | Bank of Japan | Japan CPI, labour, GDP, BoJ decision/statement, policy rate, JGB context |
| AUD | Australia | RBA | ABS CPI / labour / activity, RBA decision/statement, cash rate, ACGB context |
| CAD | Canada | Bank of Canada | StatCan CPI / LFS / GDP, BoC decision, overnight rate, GoC yields |
| CHF | Switzerland | SNB | SFSO/SECO CPI / KOF / GDP, SNB decision, policy rate, Swiss yields |

Relative information (USD vs EUR, etc.) is a **derived** class. It is only as causal as both legs’ vintages.

---

## Stage 5 — Event taxonomy

Small predeclared map. Provider-specific names collapse into these. Do not expand into hundreds of event names after seeing results.

| Research category | Examples of provider labels (illustrative, not an authorized list to mine) |
| --- | --- |
| `inflation` | CPI, CPI core, HICP, PCE, PPI |
| `employment` | NFP, unemployment rate, average earnings, labour-force survey |
| `growth` | GDP advance / preliminary / final |
| `business_surveys` | ISM, PMI, Ifo, Tankan, NAB |
| `retail_activity` | Retail sales, industrial production |
| `cb_rate_decision` | FOMC, ECB, MPC, BoJ, RBA, BoC, SNB rate decision |
| `cb_communication` | Statement, press conference, minutes, MPR, Summary of Opinions |
| `other_major_scheduled` | Only if predeclared before results (e.g. US jobless claims). Default: **exclude** |

First experiment, if later authorized, should use a **subset**: `inflation`, `employment`, `cb_rate_decision` (and optionally `growth`). Surveys and “other” stay off the first pass.

---

## Stage 6 — Provider feasibility research

Public documentation / web research only. No historical dataset download. No paid probe. Uncertain fields are **UNKNOWN**.

### Official / free statistical systems

| Source | Historical coverage | Clock-time | Actuals | Consensus | Revisions / vintage | API / export | Cost / license | Reproducibility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **FRED / ALFRED** (St. Louis Fed) | Long; series-dependent | Vintage is **date**, not intra-day clock | Yes (many US + some international series FRED hosts) | **No** | Yes: `realtime_start` / `realtime_end`, `output_type=4` first release, `/fred/series/vintagedates` | Free API, key required; docs state ≤ ~2 req/s before HTTP 429 | Free access; terms allow personal/educational use and put **additional restrictions on commercial use** — whether this research counts as commercial is **UNKNOWN / needs human legal read** | High if series IDs and vintage params are stored |
| **BLS** | Employment/CPI/PPI official | Release **schedules** publish clock times (typically 08:30 ET). API itself returns values/footnotes, **not** vintage timestamps | Yes | **No** | CES vintage tables (employment) exist as Excel/CSV; CPI vintage via ALFRED is the practical machine path | Public API v2 (registration, 500 queries/day documented) | Free | High for values; clock-time must be joined from the schedule, not the series API |
| **ONS (UK)** | CPI / labour / GDP | Publication often **07:00 UK**; landing pages keep **previous versions** with superseded timestamps | Yes | **No** | Previous-version files + versioned dataset API (`/datasets/.../versions/{n}`) | Public API | Free | High if version numbers stored |
| **Eurostat** | EA/EU statistics | Database updates 11:00 and 23:00 CET documented; that is **not** the market print clock | Current values | **No** | Official FAQ: **no data history**; updates **overwrite** previous observations | SDMX API | Free | Poor for first-print studies |
| **ECB Data Portal** | Policy rates, some macro | Policy-rate **levels** are daily; decision clock is on the press-release, not the series | Policy rates yes | **No** | `includeHistory=true` and `updatedAfter` documented. Euro Area Real-Time Database exists but is **semi-annual** experimental | SDMX API | Free | High for rate **levels**; PARTIAL for intra-day decision time |
| **StatCan WDS + real-time tables** | Canada | `releaseTime` documented as 08:30 ET; real-time tables add a **vintage = Daily release date** dimension (from ~2015, some longer; published ~1 week after the official release) | Yes | **No** | Real-time tables designed for first-print vs revision | WDS API | Free | High for vintage **dates**; clock must still be the known 08:30 rule |
| **ABS** | Australia | Indicator API: published when embargo lifts **11:30 Canberra** | Headline indicators | **No** | First-print archive in the API: **UNKNOWN** | Indicator / Data API | Free | PARTIAL |
| **BoJ / Japanese official stats** | Japan | Policy-decision clock is **not a single fixed GMT stamp** in official docs reviewed (third-party calendars often show ~03:00 GMT; treat as **UNKNOWN** until an official archive is read event-by-event) | Policy rate and many stats exist | **No** | Vintage API: **UNKNOWN** from public pages reviewed | BoJ has a data API; first-release semantics **UNKNOWN** | Free | PARTIAL / UNKNOWN |
| **SFSO / SECO / SNB** | Switzerland | SNB decisions are few (~4/year). Clock from third-party calendars (~07:30 GMT) is **not treated as official** here | Official series exist | **No** | Machine vintage: **UNKNOWN** | PARTIAL | Free | UNKNOWN |
| **US Treasury Fiscal Data / H.15** | Daily yields | Daily close / business-day, **not** M5 | Yields | **No** | Occasional restatements possible; typically low revision vs macro prints | Treasury pages + FRED DGS* | Free | High as **daily regime**, not event-time |

### Commercial / third-party calendars

| Source | What public docs claim | Consensus | Vintage | Cost | Research stance |
| --- | --- | --- | --- | --- | --- |
| **Econoday** | US archive from **2001**, key non-US from **2003**. Advertises **actual-as-initially-reported**, proprietary panel consensus (median of ~20 economists), **initial revision**, release timestamps. REST API includes `/geteventsbyrange` and `/geteventdetails`. | **Claimed historical** | **Claimed** (this is their product thesis: others overwrite) | **UNKNOWN** (enterprise / contact sales; no public price found) | Best **documented** match to AS-KNOWN-AT-TIME among calendar vendors reviewed. **Unverified** by us. Not purchased. |
| **Trading Economics** | Calendar API with `Date` (docs: UTC), `Actual`, `Previous`, `Forecast` (survey), `TEForecast` (their model), `Revised`, `LastUpdate`, `Importance` 1–3, `DateSpan` precision flag. Separate **point-in-time** page claims events “exactly as they appeared on a specific date.” | **Claimed** survey + separate proprietary `TEForecast` | **Claimed** PIT. Whether `Forecast` is the last pre-release survey and is never overwritten in the default (non-PIT) endpoint is **UNKNOWN** without a sample | Official matrix requires an account. Third-party June 2026 listings: Standard ~**$149/mo** and Professional ~**$299/mo** billed yearly; trial 100k points / 100 requests; `guest:guest` discontinued. Treat prices as **unofficial** | Usable **only after** a licensed PIT sample passes E1–E3. `TEForecast` is **not** market consensus. |
| **OANDA Labs calendar** | Legacy `GET labs/v1/calendar`, still wrapped by `oandapyV20`. Docs/community: up to **1 year**, fields `timestamp`, `actual`, `forecast`, `previous`, `market`, `impact`. Current official support status: **UNKNOWN**. | Field exists; whether historical rows keep pre-release forecast: **UNKNOWN** | **UNKNOWN**; likely latest snapshot | Included with an OANDA token; still a **dataset download** (not authorized here) | Do not use as a vintage source until a later authorized **metadata probe** proves it. 1-year cap may not cover a longer development window. |
| **MQL5 / MetaTrader calendar** | `CalendarValueHistory` returns `time`, `actual_value`, `forecast_value`, `prev_value`, `revised_prev_value` | Field exists; survey origin **UNKNOWN** | Whether history is first-print or overwritten: **UNKNOWN** | Free inside MT5; license for export/research: **UNKNOWN** | Not in this stack. Do not scrape the terminal to invent a vendor. |
| **Forex Factory** | Public calendar UI. Notices: FEED (events, ratings, descriptions, historic data) is a protected compilation; **copying / republication / redistribution is prohibited**. | Visible on the site | Overwrite vs history: **UNKNOWN**; legally irrelevant because scraping is disallowed | N/A | **Do not scrape. Do not acquire.** |
| **Investing.com / FXStreet** | Retail calendars. No licensed research API reviewed here. | Displayed | **UNKNOWN** | N/A | Treat as **scrape-unfriendly / not researchable** without a written license. |
| **Bloomberg ECO / Data License** | Terminal/enterprise consensus, surprises, timestamps. | Yes (industry default) | Generally yes in paid ECO history | **UNKNOWN** (enterprise; not public) | Capable in principle. Not obtainable under “no paid purchase.” |
| **LSEG / Refinitiv** | Datastream / workspace calendars and Consensus Economics as a premium add-on on some platforms. | Often yes | Platform-dependent | **UNKNOWN** (enterprise) | Same as Bloomberg: capable, not authorized. |
| **Consensus Economics** | Monthly (and some higher-frequency CCF) **survey** history from **1989**. Public Excel-module prices e.g. G7+WE **US$6,580/yr** historical+updates; Asia Pacific **US$4,588/yr**. | Yes, but **monthly survey**, not the 08:30 event-level “Bloomberg survey” | Survey-date vintage is defensible **for that survey date**, not as the last print-eve consensus | Public for those Excel modules | Wrong frequency for M5 surprise. Useful only as slow regime expectation, if ever licensed. |
| **Philadelphia Fed SPF** | Quarterly US survey, public. | Yes, quarterly | Survey vintage dated | Free | Not event-level. Not a substitute for NFP/CPI surprise. |

Do not invent capabilities beyond the table. Several “calendars” show forecast/actual columns **today**; that is not proof they store **as-known-then**.

---

## Stage 7 — Official macro sources

Official agencies are the right place for **actuals** and, where they publish them, **vintages**. They are the wrong place for **market consensus**.

| Need | Official sources |
| --- | --- |
| First-release actual | Often yes: ALFRED first-release, BLS CES vintage, ONS previous versions, StatCan real-time tables, ECB `includeHistory` for some series |
| Release **date** | Often yes |
| Release **clock time** | Sometimes via a **separate schedule** (BLS 08:30 ET, ONS 07:00 UK, StatCan 08:30 ET, ABS 11:30 Canberra, FOMC statement “for release at 2:00 p.m. ET”). Not usually inside the statistical API |
| Revision history | Uneven. Eurostat: **no**. ALFRED/BLS CES/ONS/StatCan/ECB: **partial to good** |
| Machine-readable | Yes for the large agencies above; weaker for SNB/BoJ vintage |
| Market consensus | **No. Documented distinction.** Surprise cannot be built from official files alone |

Prefer official actuals over a vendor’s restated actual **when** the official first print and a clock-time schedule can both be stored. Prefer a vendor **only** for consensus and for a unified multi-country clock.

---

## Stage 8 — Consensus data

This is the critical stage.

**Finding:** historically timestamped **pre-release** consensus is **not** in the repo, **not** on official APIs, and **not independently verified** from any vendor.

| Question | Answer |
| --- | --- |
| Is consensus historical at official agencies? | **No** |
| Is event-level consensus timestamped anywhere we can use for free? | **Not verified.** OANDA/MQL5/FF show a forecast column; vintage integrity **UNKNOWN** and FF is legally blocked |
| Can we establish a forecast existed before the release? | Only if a vendor stores `consensus_asof_utc` or a PIT snapshot **before** `actual_publication_ts_utc`. Econoday and TE **claim** this. We have not seen a sample |
| Do providers revise/overwrite consensus history? | Econoday **claims others do** and that they do not. TE default calendar vs PIT: **UNKNOWN** without two retrievals of the same event |
| Is historical access included in a free tier? | Not in a form that satisfies Stage 3. TE trial exists but is a paid-product on-ramp and was **not** used |
| Export / API? | Econoday REST, TE REST — both licensed. Bloomberg/LSEG — enterprise |
| Licensing? | Commercial calendar data is licensed; FF explicitly forbids copying |

**Rule carried forward:** without a defensible historical consensus, **do not** propose a macro-surprise study that silently substitutes TEForecast, an ARIMA, last month’s actual, or “the number on the website today.”

Philadelphia Fed SPF and Consensus Economics monthly surveys are **not** a workaround for event-level surprise.

---

## Stage 9 — Central bank information

| Bank | Scheduled metadata | Decision actual | Consensus expectation | Statement / PC / minutes | Notes |
| --- | --- | --- | --- | --- | --- |
| **Fed (USD)** | FOMC calendars and “for release at 2:00 p.m. ET” on statements (unscheduled emergencies exist) | Target range; FRED `DFEDTARU` / `DFEDTARL` are **daily effective levels**, not announcement clocks | Not official | Statement at decision; press conference typical; minutes later (lag is known only after the schedule is published) | Decision **level** is official and easy. Decision **surprise** needs a vendor or market-implied path (OIS), which is a different dataset |
| **ECB (EUR)** | Governing Council calendars; press conference typically after the decision | Policy rates via ECB Data Portal | Not official | Statement + PC; accounts later | Same split: level vs surprise vs text |
| **BoE (GBP)** | Official MPC date pages; Bank states publication **12:00 UK** with minutes **at the same time** | Bank Rate; voting-history spreadsheet exists | Not official | Minutes contemporaneous; MPR quarterly | One of the cleaner official clocks |
| **BoJ (JPY)** | Meeting calendars exist; **exact release minute is UNKNOWN** from official pages reviewed (third-party ~03:00 GMT) | Policy rate exists | Not official | Statement; press conference; Summary of Opinions later | Clock-time is the weak field |
| **RBA (AUD)** | Board dates published; third-party clocks ~03:30 GMT are **not** treated as official here | Cash rate | Not official | Statement | Official minute **UNKNOWN** until the statement archive is read |
| **BoC (CAD)** | Dates published; third-party ~13:00/14:00 GMT **not** treated as official | Overnight rate | Not official | Statement / MPR | Official minute **UNKNOWN** until archive read |
| **SNB (CHF)** | Quarterly-ish; third-party ~07:30 GMT **not** treated as official | Policy rate | Not official | Statement | Sparse n |

**Do not design NLP.** Text/document content is a separate, later, licensed problem. For a first experiment, `cb_rate_decision` uses **time + rate level**, not speech text.

Expected decision (consensus) is the same Stage 8 problem. Market-implied probabilities (Fed funds futures / OIS) are **another** paid/market dataset and are not in this repo.

---

## Stage 10 — Rate / yield data

| Series class | Frequency | Timestamp semantics | Revision risk | Coverage | Cost | Fit to M5 vs regime |
| --- | --- | --- | --- | --- | --- | --- |
| Policy target / facility rates | Changes on decision days; stored daily | Daily **effective** date ≠ announcement minute | Low | All 7 currencies exist officially | Free | **Regime / pair context.** Not an M5 trigger unless joined to a decision clock |
| US Treasury CMT (FRED `DGS2`, `DGS10`, …) | Daily | Business-day yield; FRED `last_updated` is a load time, not the Treasury print clock | Low–medium | USD | Free (FRED terms as above) | Slow differential / carry context |
| Other sovereign 2y/10y | Daily | Same limitation | Low–medium | EUR/GBP/JPY/AUD/CAD/CHF via national banks, FRED mirrors, or paid vendors | Official: PARTIAL. Vendor: paid | Same |
| Money-market (SOFR, SONIA, €STR) | Daily | Official publish calendars exist; still not M5 | Low | USD/GBP/EUR strong; others PARTIAL | Free official | Slow |
| Yield differential (e.g. US 2y − DE 2y) | Daily | Derived; both legs must be as-known | Medium if either leg revises | Derived | Depends on legs | **Hypothesis E only.** Never treat as a bar-by-bar BUY/SELL |

**Do not assume daily rates provide M5 timing.** A rate that is constant across hundreds of M5 bars destroys event independence if every bar is sampled.

---

## Stage 11 — News / text feasibility

High level only. No scrape. No NLP design.

| Question | Answer |
| --- | --- |
| Can historically timestamped text be obtained? | Yes, from **LSEG Machine Readable News** (Reuters archives documented back to **1996**, timestamps in UTC) and **Dow Jones / Factiva Snapshots**. These are enterprise contracts |
| Are timestamps publication-time reliable? | For those paid feeds, docs claim normalized UTC publication times. For websites/RSS, **no** |
| Is historical licensing practical? | **No** for this project at the current authorization level. Pricing is not public; rights include retention and text-mining clauses |
| Can revisions/updates be distinguished? | On paid newswires, often yes (story versions). On scraped HTML, no |
| Can source timestamps be reconstructed causally? | Only from a feed that stored them. Reconstructing from later web copies is not causal |

**Historical news/text is not practical** for Quant V2 next. Expensive, legally constrained, and unnecessary before a **numeric** calendar experiment exists.

---

## Stage 12 — Alignment with existing M5 / M1

Reuse Experiment C candle semantics. OANDA `time` is **bar start**. An M5 bar `[t, t+5m)` is knowable at `t+5m`. An M1 bar is knowable at its end.

### Join rules

1. Store every external timestamp in **UTC**. Keep the published local timezone as metadata.
2. **DST:** convert with the **historical** timezone rule (America/New_York, Europe/London, Australia/Sydney, …), not a fixed GMT offset. `tzdata` is already a dependency.
3. **Scheduled event, pre-event features:** last eligible completed market bar **ends** at or before `scheduled_ts_utc`. Minutes-to-event is known before the print and **must be dropped** after the print.
4. **Actual release, post-release labels:** first eligible M5 start is the first M5 with `bar_start ≥ actual_publication_ts_utc`. First eligible M1 start is the first M1 with `bar_start ≥ actual_publication_ts_utc`. Never use M1 minutes that form a bar whose start is before the actual.
5. If only a scheduled clock exists and the actual clock is missing, **do not** attach actual/surprise to market data. Proximity-to-schedule is still allowed using the schedule only.
6. If only an ALFRED **date** exists, treat publication time as **UNKNOWN**. Do not assume 00:00 UTC. Optionally, if an **independent official schedule** for that same release says 08:30 ET, the join may use that schedule — and must record that the clock came from the schedule, not ALFRED.
7. **Weekends / holidays:** FX week close remains 21:00 UTC Friday (existing bot convention). Events in the weekend gap have no first eligible bar until Sunday open. Label those `MARKET_CLOSED`.
8. **Simultaneous releases:** one research row per `(timestamp, currency, research_category)`. If two categories print at the same instant (US CPI + real earnings), do **not** explode into combinatorial interactions on the first experiment. A later predeclared “US 08:30 cluster” flag is allowed as a single boolean.
9. **Multiple events at the same timestamp across currencies:** allowed as separate rows. Relative-surprise hypotheses need **both** legs’ actual clocks.
10. **M1 path labels** after a release reuse Experiment C first-touch hurdles (1.0× / 1.5× / 2.0× / 3.0× contemporaneous M5 completed-bar half-spread from Experiment A). Spreads **widen** into news; the hurdle must be the event-bar (or first post-release bar) half-spread, not 1.0 pip fiction.
11. Date-only rows, estimated clocks (`DateSpan=1` in TE terms), and missing M1 coverage are `INSUFFICIENT_DATA`, not invented order.

---

## Stage 13 — Future hypotheses (designed, not tested)

Five only. No optimization. No combination with A/B variables on the first pass (Stage 14).

### A — Scheduled high-impact proximity predicts magnitude

- **Class:** PRE-EVENT MAGNITUDE
- **Information at decision time:** schedule, category, currency, minutes-to-event. **No actual. No surprise.**
- **Target:** absolute 60m / 240m excursion vs non-event base rate; fraction of events with BOTH-sided 1× and 2× cost hurdles
- **Horizon:** 60m and 240m predeclared
- **Expected n:** ~80–150 high-impact prints in one year across 7 currencies if the set is CPI + employment + CB decisions (order-of-magnitude; exact n UNKNOWN until a schedule is collected)
- **Cost relevance:** useful if it changes **whether** 1× contemporaneous spread is reachable, or ranks two-sided expansion. Not a direction claim
- **Major leakage:** inferring “high-impact” from later realized vol; using post-release actuals
- **Falsification:** event-window abs excursion CI overlaps the matched non-event base rate, or only reproduces Experiment A activity ranking

### B — Standardized macro surprise predicts currency-direction response

- **Class:** POST-RELEASE DIRECTION
- **Information at decision time:** `actual_first`, `consensus` with `asof ≤ publication`, surprise in units of historical TRAIN IQR or official unit
- **Target:** signed pair move in the **event currency vs USD** (or USD vs others for USD events) after `actual_publication_ts_utc`
- **Horizon:** 15m / 60m / 240m predeclared, not cherry-picked
- **Expected n:** same as A **only if** consensus exists for every row; otherwise much smaller
- **Cost relevance:** G3 on unique signed close or unique M1 first-touch vs **that bar’s** half-spread
- **Major leakage:** hindsight consensus; revised actual; aligning to scheduled rather than actual clock
- **Falsification:** signed mean inside 1× cost, or UP_FIRST − DOWN_FIRST ≈ 0 after M1 resolution
- **Blocked until Stage 8 is solved**

### C — Relative surprise predicts pair direction

- **Class:** POST-RELEASE DIRECTION
- **Information:** surprise_A − surprise_B for the two currencies in the pair, both causally available
- **Target:** signed pair close / M1 path
- **Horizon:** 60m / 240m
- **Expected n:** simultaneous or same-week pairs; **much smaller** than B
- **Cost relevance:** G3 on the traded pair
- **Major leakage:** using a later print on one leg; hunting pairs after seeing results
- **Falsification:** no stable sign after cost
- **Blocked until B’s data exists.** Do not run C as the first experiment.

### D — Policy-rate surprise predicts post-decision direction

- **Class:** POST-RELEASE DIRECTION
- **Information:** announced rate vs pre-decision expected rate (vendor survey **or** a predeclared market-implied series with its own vintage)
- **Target:** signed currency vs USD after the **statement clock**
- **Horizon:** 60m / 240m / 1 trading day
- **Expected n:** ~8 Fed + 8 ECB + 8 BoE + ~8 BoJ + ~11 RBA + 8 BoC + 4 SNB ≈ **50–60 / year**. Thin. Multi-year history required
- **Cost relevance:** G3; news spreads widen
- **Major leakage:** using the daily FRED target as if it printed at 00:00; using later minutes text
- **Falsification:** n too small or effect < cost
- **Blocked until expected-rate vintage exists**

### E — Rate differential provides slower directional / regime context

- **Class:** SLOW CONTEXT (not M5 timing)
- **Information:** as-known daily 2y (or policy-rate) differential
- **Target:** non-overlapping H1 / H4 / 1d signed close, **not** every M5
- **Horizon:** 4h / 1d / 5d predeclared
- **Expected n:** ~250 daily observations / year / pair — independence is daily, not 75k M5 bars
- **Cost relevance:** spread is a smaller fraction of a 1d move **if** a move exists; edge still required
- **Major leakage:** overlapping 5-day labels on every M5; using revised yields
- **Falsification:** sign unstable across years or fails after cost on non-overlapping holds
- **Not the first experiment.** Different timeframe question from V1/A/B/C.

---

## Stage 14 — Interaction with A/B context

Experiment A: activity ranks **magnitude**. Experiment B: dispersion ranks **magnitude**. Residual reversal was statistically detectable and below G3.

A future macro experiment **tests external information alone first**.

Predeclared later possibilities — **not** to be run until the external series has independent evidence:

1. High-activity ∩ scheduled-event-window (magnitude only).
2. High-dispersion ∩ scheduled-event-window (magnitude only).
3. Residual-extreme ∩ post-surprise (only if Hypothesis B independently clears gates).

Do not grid activity quintiles × dispersion quintiles × event types × horizons. That is combinatorial mining.

---

## Stage 15 — Holdout problem

2025-09 through 2026-08 is **DEVELOPMENT / DISCOVERY**. It has been inspected for V1 events, A spread/volume, B residuals, and C M1 paths. Joining a **new** calendar to those same prices does **not** create a pristine final holdout.

Honest development options:

| Option | Role |
| --- | --- |
| Older market + older calendar (e.g. 2022–2024, or `backtest.py` regime years **only if** M5 and a vintage calendar both exist) | Extra **development** folds. Still not a final holdout once inspected |
| Walk-forward inside development | Required chronology check. Does not un-inspect the year |
| Newer **future** months after the last inspected bar | Only these can become an untouched holdout, and only if they are **not** used for discovery |
| A later locked final holdout | Must be declared **before** looking at its external-joined results |

**Explicit rule:** adding a new feature to an old inspected price period does **not** magically make that period a pristine final holdout.

If the first external experiment is run on DEV0, label every result **DISCOVERY**. G3 still applies. Training still does not.

---

## Stage 16 — Source scorecard

Scores are factual categories, not a purchase recommendation. **UNKNOWN** is shown.

| Source | Causal historical quality | Vintage quality | Consensus | Timestamp quality | Currency coverage | API / export | Licensing / cost | Reproducibility | Leakage risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FRED/ALFRED | HIGH for US actuals | HIGH for **dates** | **NONE** | LOW–MED (date, not clock) | MED (USD strong; others via hosted series) | HIGH | FREE with commercial-use **UNKNOWN** | HIGH | MED (clock assumption) |
| BLS + official schedule | HIGH | HIGH (CES vintage + ALFRED) | **NONE** | HIGH if schedule joined | USD only | HIGH | FREE | HIGH | LOW if schedule is the historical one |
| ONS versions | HIGH | HIGH (file versions) | **NONE** | HIGH (07:00 UK typical) | GBP | HIGH | FREE | HIGH | LOW |
| Eurostat | LOW for first-print | **NONE** (overwrite) | **NONE** | LOW | EUR | HIGH | FREE | LOW for vintages | HIGH if used as first-print |
| ECB Data Portal | HIGH for rate **levels** | MED (`includeHistory`; RTD semi-annual) | **NONE** | MED (level vs statement clock) | EUR | HIGH | FREE | HIGH for levels | MED |
| StatCan real-time | HIGH | HIGH (vintage date) | **NONE** | HIGH clock convention (08:30 ET) | CAD | HIGH | FREE | HIGH | LOW–MED (tables lag ~1 week) |
| ABS | MED | UNKNOWN | **NONE** | HIGH clock convention (11:30 Canberra) | AUD | HIGH | FREE | PARTIAL | MED |
| BoJ / SNB official | PARTIAL | UNKNOWN | **NONE** | UNKNOWN clock | JPY / CHF | PARTIAL | FREE | UNKNOWN | MED–HIGH |
| Econoday | HIGH **if claims hold** | HIGH **if claims hold** | **CLAIMED** | CLAIMED | CLAIMED US+intl | HIGH (licensed API) | PAID, price UNKNOWN | HIGH if licensed | LOW **if** audit passes |
| Trading Economics PIT | MED–HIGH **if PIT works** | CLAIMED | CLAIMED survey + separate model | CLAIMED UTC + DateSpan | HIGH country list | HIGH (paid) | PAID, ~$149–299/mo **unofficial** | HIGH if key+query stored | MED until PIT vs live compared |
| OANDA Labs calendar | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | Pair-relevant | HIGH (token) | Token already held; still a download | MED | HIGH until audited |
| MQL5 calendar | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | Broad | MT5 only | UNKNOWN | LOW here | HIGH |
| Forex Factory | N/A | N/A | N/A | N/A | Broad UI | No official API | **Prohibited copy** | N/A | Do not use |
| Bloomberg / LSEG | HIGH | HIGH | YES | HIGH | HIGH | HIGH | PAID UNKNOWN enterprise | HIGH | LOW |
| Consensus Economics monthly | HIGH for monthly surveys | HIGH at survey date | YES (wrong frequency) | Survey date | G7/APAC modules | Excel / platforms | Public ~$3.5k–$6.6k/yr per module | HIGH | HIGH if used as event surprise |
| LSEG/DJ news | HIGH | Versioned stories | N/A (text) | HIGH on paid feed | Broad | HIGH | PAID UNKNOWN | HIGH | Licensing / cost |

---

## Stage 17 — Minimum viable external dataset

Smallest dataset that would justify **the first** external-information experiment. Prefer narrow high-quality over a huge questionable calendar.

**Experiment class:** Hypothesis A only (scheduled proximity → magnitude). No surprise.

| Item | Requirement |
| --- | --- |
| Event categories | `inflation`, `employment`, `cb_rate_decision` |
| Currencies | **USD, GBP, CAD** first (best official clocks). Add EUR/AUD if official clocks are confirmed. JPY/CHF only with an official minute, not a third-party guess |
| Required fields | `event_id`, `research_category`, `currency`, `scheduled_ts_utc`, `scheduled_tz_source`, `scheduled_precision=clock`, `source_agency`, `retrieval_ts_utc`. Actuals **optional** for A. Consensus **absent** |
| Minimum history | Enough events for event-level bootstrap: target **≥ 80 events** after filters. One year of the three-currency core is a plausible start (~70–120). If n < 40, do not test |
| Timestamp | Clock, UTC, DST-correct. Date-only rows dropped |
| Vintage | Schedule must be the **historical** schedule (archived year pages / stored ICS as-of), not today’s revised calendar |
| Consensus | **Not required** for this minimum set. If a row has consensus, store it unused |

A surprise dataset (Hypothesis B) is a **superset**: the above **plus** `actual_first`, `actual_publication_ts_utc`, `consensus_forecast`, `consensus_asof_utc`, first-release vs revision flags. That superset is **not** minimum-viable until E3 passes.

---

## Stage 18 — Acquisition plan (designed, not executed)

No download. No purchase.

### Path 0 — Do nothing until the human picks a path

Default after this task.

### Path 1 — Official-schedule metadata (free, Hypothesis A)

| Item | Plan |
| --- | --- |
| Source | BLS year schedules / ICS; FOMC calendars + statement “for release at”; ONS release calendar / previous-version stamps; StatCan The Daily / WDS `releaseTime`; BoE MPC date pages (12:00 UK); ECB Governing Council pages; ABS release clock if confirmed |
| Fields | Stage 17 minimum |
| Date range | Prefer a **pre-DEV0** window if M5 can be obtained later; if joining DEV0, label DISCOVERY. Do not pretend DEV0 is holdout |
| Method | Manual/scripted fetch of **official HTML/ICS/API metadata only**, one agency at a time, with resume |
| Rate limits | BLS API 500/day if used; ICS/HTML polite pacing. No broker write endpoints |
| Storage | `data/research/external/raw/<agency>/<retrieval_date>/` immutable; `data/research/external/normalized/events.parquet` derived |
| Identity | SHA-256 of each raw file; row counts; agency; retrieval UTC |
| Vintage | Keep raw pages; never overwrite; new retrieval = new directory |
| Resume | Per-agency checkpoint JSON |
| Not included | Consensus, news, TEForecast, FF |

### Path 2 — Official first-print actuals (free, still no surprise)

ALFRED `output_type=4` + BLS CES vintage + ONS versions + StatCan real-time tables, joined to Path 1 clocks. Same immutable raw layout. FRED API key required; respect 2 req/s. Commercial-use terms: human review.

### Path 3 — Licensed PIT calendar (paid, only after quote)

Econoday **or** Trading Economics PIT, not both on the first buy. Fields = Stage 2 full set. Date range: at least two years if surprise (Hypothesis B/D) is the goal, because CB n is thin. Store vendor vintage id. Immediately run E1–E3 on a **small** sample (one US CPI year + one FOMC year) **before** a full pull.

### Path 4 — Explicitly rejected

Forex Factory scrape. Investing.com / FXStreet scrape. Using OANDA Labs or MQL5 as if they were vintage-audited. Buying news/text. Buying Consensus Economics monthly as a fake event surprise.

### Expected shape (if Path 1 is later authorized)

Hundreds of rows, not millions. A year of the Stage 17 subset is a small CSV. Checksums matter more than size.

---

## Stage 19 — Go / no-go gates (before acquisition)

| Gate | Requirement | Fail if |
| --- | --- | --- |
| **E1** | Historical timestamps are causal and clock-reliable (UTC, DST, `scheduled_precision=clock`) | Date-only, estimated clocks, or clocks inferred from price |
| **E2** | First-release / vintage semantics are defensible for any **actual** used | Latest-database values, Eurostat-style overwrite, undocumented revision |
| **E3** | Consensus is truly pre-release **if surprise is required** | Missing `asof`, overwritten forecast, TEForecast/ARIMA substitute |
| **E4** | Coverage sufficient: target ≥ 80 clock-stamped events across ≥ 2 currencies for Hypothesis A; Hypothesis D needs more **years**, not more event types |
| **E5** | Licensing permits this research use (official terms + any vendor contract). FF-style prohibition is an automatic fail |
| **E6** | Only after E1–E5, a **separate** human authorization may acquire that specific path |
| **E7** | Information study before any model training. No `_quant_stub_vote`, no filters, no BUY/SELL change |
| **G3** | Unchanged: economically useful **direction** must clear contemporaneous half-spread. Magnitude-only results cannot authorize trades |

E3 is **failed today** for any surprise study. E1 is **not yet demonstrated** on an assembled file. Therefore E6 is **closed**.

---

## Stage 20 — Final recommendation

1. **Is defensible historical scheduled-event data obtainable?** **Partially yes.** Official US/UK/CA (and likely EA/AU) schedules and clocks exist. A unified seven-currency clock-stamped archive is **not** sitting in the repo and is **not** fully verified for JPY/CHF official minutes. Vendor calendars claim to unify this if licensed.

2. **Is defensible historical actual-release data obtainable?** **Yes for several official series** (ALFRED first-release, BLS CES vintage, ONS versions, StatCan real-time, ECB history parameter). **No** from Eurostat’s live API. Clock-time still has to come from a schedule.

3. **Is defensible pre-release consensus obtainable?** **Not from official sources. Not verified from any vendor. Not free in a form that passes Stage 3.** Econoday/TE/Bloomberg **claim** it. This task did not inspect a sample.

4. **Can macro surprise be reconstructed without hindsight?** **Not yet.** Do not run Hypothesis B/C/D.

5. **Are central-bank decisions feasible?** **Levels: yes.** **Clocks: yes for Fed (2:00 p.m. ET typical) and BoE (12:00 UK); PARTIAL/UNKNOWN for others without reading each official archive.** **Expected decision: no** without a vendor or a separate market-implied series.

6. **Are rates/yields feasible?** **Yes as daily regime context** (FRED DGS*, official policy rates). **Not** as M5 timing.

7. **Is historical news/text practical?** **No.** Enterprise licensing, non-public cost, unnecessary before a numeric calendar exists.

8. **Minimum viable external dataset?** Stage 17: clock-stamped `inflation` + `employment` + `cb_rate_decision` for **USD/GBP/CAD**, no consensus, Hypothesis A only.

9. **Which source(s) could provide it?** Path 1 official schedules (BLS, Fed, ONS, BoE, StatCan; ECB/ABS if clocks confirm). Optional later: Econoday or TE PIT **after** a quote and a sample audit. Not FF, not scraped retail calendars.

10. **Cost / requirements?** Official path: free APIs + human time + FRED key + legal read of FRED commercial terms. TE: unofficial ~$149–$299/month. Econoday/Bloomberg/LSEG: unknown enterprise. Consensus Economics monthly modules: public thousands of USD/year and **wrong frequency**. News: unknown enterprise. No purchase is authorized now.

11. **Biggest leakage risk?** Using a **hindsight consensus or revised actual**, or treating a **date-only vintage** as an M5 publication time. Secondary: using today’s impact ratings; inferring events from volatility.

12. **What should the FIRST external-information experiment test?** **Hypothesis A alone:** does scheduled high-impact proximity change **magnitude / tradeability** versus a non-event base rate, using contemporaneous Experiment A half-spread, without actuals or surprise. That is the only experiment whose data requirements are close to being satisfiable without a paid vintage audit.

13. **Should any data acquisition be authorized next?** **Not by this task.** Human review should choose: (i) stay stopped, (ii) later authorize Path 1 official-schedule metadata only, or (iii) obtain a vendor quote and later authorize a **small** PIT sample for E1–E3. Do not authorize surprise data, news, or a full paid calendar dump.

**Returned verdict:** `EXTERNAL_DATA_FEASIBILITY_INCOMPLETE`

---

## What was not done

- No external macro / calendar / rate / news download
- No paid subscription or trial API pull
- No OANDA Labs calendar probe
- No production / `_quant_stub_vote` / BUY/SELL / SL/TP / ATR / risk / session / RL / API / execution change
- No macro signals or event filters
- No model training
- No Docker or live-bot restart

Wait for human review.
