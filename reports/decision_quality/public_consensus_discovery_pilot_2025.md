# Public pre-release consensus discovery — 2025 six-event pilot

**Status:** STAGE 2A PILOT COMPLETE — research only. Stop here. Do not scale to all 2025 events until this report is reviewed.

Stage 1 first prints remain authoritative. They were not replaced with news-article values. No FX backtest. No production, live strategy, OANDA, Docker, or bot change.

Machine-readable records: `data/research/macro_consensus/pilot/` (`schema.json`, `observations.json`, `observations.csv`, `events_investigated.json`).

Econoday is **not** ingested. Each observation has a reserved `econoday_consensus_value` field left null.

---

## EVENTS INVESTIGATED

Six verified Stage 1 events, spread across 2025:

| event_id | Official release UTC | Stage 1 first print | Stage 1 status |
| --- | --- | --- | --- |
| `CPI_2024-12_2025-01-15` | 2025-01-15T13:30:00Z | H MoM 0.4 / H YoY 2.9 / C MoM 0.2 / C YoY 3.2 | VERIFIED_FIRST_PRINT |
| `CPI_2025-04_2025-05-13` | 2025-05-13T12:30:00Z | 0.2 / 2.3 / 0.2 / 2.8 | VERIFIED_FIRST_PRINT |
| `CPI_2025-08_2025-09-11` | 2025-09-11T12:30:00Z | 0.4 / 2.9 / 0.3 / 3.1 | VERIFIED_FIRST_PRINT |
| `EMPLOYMENT_SITUATION_2024-12_2025-01-10` | 2025-01-10T13:30:00Z | NFP 256000 / UE 4.1 / AHE 0.3 / 3.9 | VERIFIED_FIRST_PRINT |
| `EMPLOYMENT_SITUATION_2025-05_2025-06-06` | 2025-06-06T12:30:00Z | 139000 / 4.2 / 0.4 / 3.9 | VERIFIED_FIRST_PRINT |
| `EMPLOYMENT_SITUATION_2025-09_2025-11-20` | 2025-11-20T13:30:00Z | 119000 / 4.4 / 0.2 / 3.8 | VERIFIED_FIRST_PRINT |

October 2025 unpublished BLS prints were not used. November 2025 CPI (two-month / AMBIGUOUS) was not used.

---

## VERIFIED PRE-RELEASE CONSENSUS COVERAGE

`VERIFIED_PRE_RELEASE` requires an identifiable source, an identifiable consensus number, the correct indicator, a publication **clock** demonstrably before official release, and clear survey/consensus semantics.

| Event | Verified pre-release? | Clocked source | What cleared the bar |
| --- | --- | --- | --- |
| CPI Dec 2024 | YES, weakly | Calculated Risk 2025-01-14T13:12:00Z | Unnamed "consensus" with a clock. Provider is UNKNOWN. |
| CPI Apr 2025 | NO | none | Date-only FinancialJuice forecast table only. FactSet preview not found. |
| CPI Aug 2025 | NO | none | Reuters survey exists on a Sept 10 PPI article, but **date only**. |
| Emp Dec 2024 | NO | none | FactSet and FinancialJuice exist, date only. CNN page timed out. |
| Emp May 2025 | YES | WTAQ Reuters reprint 2025-06-06T05:38:00Z | Reuters survey NFP / UE / AHE MoM / AHE YoY. |
| Emp Sep 2025 | YES | Euronews/AP 2025-11-20T11:54:00Z | FactSet survey NFP 50000 / UE 4.3, 96 minutes before 13:30Z. |

Pilot events with at least one `VERIFIED_PRE_RELEASE` observation: **3 of 6**.

CPI verified: **1 of 3**. Employment/NFP verified: **2 of 3**.

Date-only pre-release material exists for **5 of 6** events. That is not the same as verified.

---

## SOURCE-BY-SOURCE COVERAGE

| Source | Role in the pilot | Temporal quality | Usable as systematic vintage? |
| --- | --- | --- | --- |
| FactSet Insight (John Butters) | Public median pages, often "Tomorrow BLS will release". n disclosed on several pages (8–19). CPI pages are often YoY-only. | Date only | Partial. URL pattern is guessable. April CPI page was not found. Small n. |
| Morningstar | Reprints a fuller FactSet consensus (all four CPI fields). | Date only (byline day) | Partial. Complements FactSet Insight. |
| FinancialJuice prep pages | Median / Forecast tables, sometimes n and range. Vendor usually unnamed. | Date only | Partial. Quality uneven (one page claims n=459). |
| Reuters.com | Survey language is common. Pages are often updated after the print. | Unsafe as-of without an archive or reprint | Not from live reuters.com alone. |
| Reuters wire reprints (WTAQ) | Same Mutikani preview copy with a local CMS clock. | Clock possible | Opportunistic, not a complete series. |
| Reuters adjacent-day stories | Sept 10 PPI article carried the Aug CPI Reuters survey. | Date only, but body still pre-CPI | Opportunistic. |
| AP / Euronews | Pre-release FactSet numbers with a GMT+1 clock. | Clock possible | Opportunistic. |
| Calculated Risk | Named "consensus" with an 08:12 AM clock. Provider unnamed (historically often Econoday/Briefing). | Clock | One event. Not a named survey series. |
| Bloomberg | 125k May NFP snippet appeared in search with a 23:00 UTC Jun 5 stamp. Paywalled. Not used. | Unverified | No. |
| Benzinga | Cloudflare-blocked. | None | No. |
| MUFG / bank previews | Qualitative or house numbers. | Date only | SINGLE_FORECAST only. |
| Econoday | Not used. Reserved for later comparison. | n/a | n/a |
| Today's economic-calendar Forecast field | Not used. | n/a | Forbidden for this pilot. |

---

## TIMESTAMP QUALITY

| Quality | Count of observations | Meaning |
| --- | --- | --- |
| Clock + UTC + lead time | 10 | `VERIFIED_PRE_RELEASE` (plus 1 clocked single forecast) |
| Date only | 35 | `PRE_RELEASE_DATE_ONLY` |
| Not found | 1 | April FactSet CPI page |
| Single forecast | 4 | Contrast cases, not consensus |

Clock sources used:

- Calculated Risk: `1/14/2025 08:12:00 AM` treated as America/New_York EST → `2025-01-14T13:12:00Z`. Lead **1458** minutes.
- WTAQ: `Jun 6, 2025 \| 12:38 AM` treated as America/Chicago CDT → `2025-06-06T05:38:00Z`. Lead **412** minutes. Any US civil timezone at 12:38 AM that morning is still before `12:30Z`.
- Euronews: `20/11/2025 - 12:54 GMT+1` → `2025-11-20T11:54:00Z`. Lead **96** minutes.

Date-only pages that say "tomorrow" or "Good Morning / what to look out for today" are still `PRE_RELEASE_DATE_ONLY`. The rule does not automatically promote a date to verified.

---

## REUTERS COVERAGE

**PARTIAL.**

Reuters poll wording ("economists polled by Reuters", "a Reuters survey of economists") is widespread. It is **not** generally recoverable as a timestamp-safe vintage from reuters.com:

- Live Reuters pages are often updated after the print. A current "Updated" stamp at or after release is `POST_RELEASE_ONLY` even if leftover preview sentences remain.
- The usable Reuters May NFP survey came from a **local-station reprint** (WTAQ) that kept a 12:38 AM clock.
- The usable Reuters Aug CPI survey came from a **PPI-day article** (Sept 10) that still forecast Thursday CPI and did not contain the later 0.4 print. Dateline only, so not verified.
- A Reuters.com JOLTS page that also previewed May NFP timed out and was not used.

Reuters is therefore usable when a reprint, archive, or adjacent-day article preserves pre-release copy **and** a clock. It is not a drop-in systematic source from reuters.com alone.

---

## OTHER SURVEY COVERAGE

**PARTIAL.**

- **FactSet:** the most repeatable free survey. Public Insight pages exist for Dec 2024 CPI, Dec 2024 NFP, May 2025 NFP, Aug 2025 CPI, and Sep 2025 NFP. Sample sizes are small (8–19). CPI Insight pages often omit MoM. Morningstar sometimes fills those MoM fields from FactSet. April 2025 CPI Insight page: **NOT_FOUND**.
- **FinancialJuice:** prep pages exist and are free. Vendor is usually unnamed. One NFP page reports n=459, which is not credible for a standard economist poll and is flagged.
- **AP/Euronews:** one clocked FactSet reprint (delayed Sep 2025 jobs).
- **Calculated Risk:** one clocked unnamed consensus (Dec 2024 CPI).
- **Fed / regional Fed surveys:** no contemporaneous public survey of BLS CPI/NFP consensus was found for these six events.
- **ADP:** not used as an NFP substitute.

---

## CONFLICTING VALUES

Providers were **not** averaged. Conflicts stored separately:

| Event | Indicator | Values (do not average) |
| --- | --- | --- |
| CPI Dec 2024 | Headline YoY | FactSet / Morningstar **2.8** vs FinancialJuice / Calculated Risk **2.9** |
| Emp Dec 2024 | NFP | FactSet **153000** vs FinancialJuice Jan 7 **160000** vs FinancialJuice Jan 10 morning **165000**. Reuters post-release stories commonly cite **160000**; that post-release claim is not a pre-release observation in this file. |
| Emp May 2025 | NFP | Reuters reprint **130000** agrees with FactSet **130000**. Bloomberg search snippet **125000** is paywalled and **not stored**. |
| CPI Apr 2025 | Headline MoM | FinancialJuice Forecast table **0.3** vs Wells Fargo house **0.2** on the same page (not a provider conflict of surveys). |
| CPI Aug 2025 | Headline MoM | Reuters **0.3** and FactSet-via-Morningstar **0.3** agree. Ameriprise house **0.4** is a single forecast. |
| Emp Sep 2025 | NFP | FactSet **50000** (Insight Oct 2 and Euronews Nov 20) vs Santander house **75000**. |

These disagreements are large enough that a later surprise series must be **provider-specific**. A blended "market consensus" would hide the 2.8 vs 2.9 CPI YoY split and the 153k vs 165k NFP split.

---

## PAYWALL / ACCESS PROBLEMS

- Bloomberg: paywalled. Not used.
- Reuters.com: often registration-walled; update-in-place is the larger problem.
- Benzinga: Cloudflare challenge; not used.
- CNN Jan 10 jobs page: fetch timed out; snippet not used.
- FactSet Insight and FinancialJuice and Morningstar and Euronews and Calculated Risk and WTAQ: opened successfully for this pilot.
- Direct BLS first prints were not re-fetched; Stage 1 values were reused.

Systematic collection of a Reuters vintage from the public web is blocked by paywall plus in-place updates. Systematic FactSet date-only collection is more practical but still incomplete (missing April CPI page; YoY-only CPI pages).

---

## INDICATORS AVAILABLE

CPI targets attempted: headline MoM, headline YoY, core MoM, core YoY. Missing values were not inferred.

| Event | H MoM | H YoY | C MoM | C YoY |
| --- | --- | --- | --- | --- |
| Dec 2024 | CR clocked 0.3; FJ 0.3; MS/FactSet 0.3 | Conflict 2.8 vs 2.9 | CR/FJ/MS 0.2 | 3.3 across sources |
| Apr 2025 | FJ 0.3 only (unnamed) | FJ 2.4 | FJ 0.3 | FJ 2.8 |
| Aug 2025 | Reuters/MS 0.3 | Reuters/FactSet/MS 2.9 | Reuters/MS 0.3 | Reuters/FactSet/MS 3.1 |

Employment targets attempted: NFP, unemployment rate, AHE MoM, AHE YoY. ADP not substituted.

| Event | NFP | UE | AHE MoM | AHE YoY |
| --- | --- | --- | --- | --- |
| Dec 2024 | Conflict 153k / 160k / 165k | 4.2 (FactSet + FJ) | not recovered as survey | FJ morning 4.0 |
| May 2025 | Reuters+FactSet 130000 | Reuters+FactSet 4.2 (FactSet UE month label dirty) | Reuters 0.3 | Reuters 3.7 |
| Sep 2025 | FactSet 50000 | FactSet 4.3 | not recovered | not recovered |

NFP is the only employment field with both a clocked verified observation (May, Sep) and a usable date-only FactSet series.

---

## LOOK-AHEAD RISKS

1. **Reuters.com update-in-place.** A page that still reads like a preview can carry a post-release Updated timestamp. Treating the current reuters.com clock as publication time would leak the print.
2. **Post-release "had expected" sentences.** Articles published after 08:30 ET often quote the poll. Those are `POST_RELEASE_ONLY` even when the number is the genuine pre-release poll.
3. **Today's calendar Forecast field.** Forbidden. Not used.
4. **Stale FactSet pages on delayed releases.** The Sep 2025 NFP Insight page is dated October 2, written for the original schedule. The print moved to November 20. Euronews/AP on Nov 20 still quoted 50k / 4.3, so the number appears stable, but the October page is not an as-of immediately before the delayed release.
5. **FinancialJuice quality.** One page says n=459 and mislabels the reference month as November. Do not treat FJ as equivalent to Reuters or FactSet without reading the page.
6. **FactSet UE month typo.** The May 2025 payroll page titles May payrolls but the UE paragraph says April. Stored with a quality flag.
7. **AI search summaries.** Not used as evidence. Every stored number comes from a page that was opened.
8. **Arithmetic QA column.** `qa_arithmetic_difference = Stage1_first_print - consensus` is for inspection only. It is not a surprise feature, not a trade rule, and not an FX return.

---

## SYSTEMATIC COLLECTION FEASIBILITY

A **verified-clock** Reuters/FactSet vintage for all 2025 CPI and Employment events **cannot** be built from the free public web with the standard used here.

What *could* be collected mechanically, still as research, if a later task authorizes scaling:

- FactSet Insight date-only medians for most (not all) events, YoY-heavy for CPI, small n.
- FinancialJuice prep pages, vendor unnamed, quality checks required.
- Occasional clocked reprints (AP, local Reuters affiliates, blogs). Coverage would stay incomplete.

That would produce a **date-only** panel, not a `VERIFIED_PRE_RELEASE` panel. Surprise research that needs a clean as-of timestamp should wait for a vendor vintage (Econoday sample, Bloomberg, or a Reuters poll archive) or accept provider-specific date-only FactSet as an experimental reconstruction — labelled as such, never averaged.

**Enough evidence to scale to all 2025 events under the verified-clock rule: NO.**

---

## PER-EVENT PILOT TABLE

Candidate consensus rows below are the **primary survey candidates**, not house forecasts. Official first prints are Stage 1.

### 1. CPI Dec 2024 — release 2025-01-15T13:30:00Z

Stage 1: 0.4 / 2.9 / 0.2 / 3.2

| Indicator | Candidate | Provider | Publisher | Pub time UTC | Lead (min) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| H MoM | 0.3 | UNKNOWN | Calculated Risk | 2025-01-14T13:12:00Z | 1458 | VERIFIED_PRE_RELEASE |
| H YoY | 2.9 | UNKNOWN | Calculated Risk | 2025-01-14T13:12:00Z | 1458 | VERIFIED_PRE_RELEASE |
| C MoM | 0.2 | UNKNOWN | Calculated Risk | 2025-01-14T13:12:00Z | 1458 | VERIFIED_PRE_RELEASE |
| C YoY | 3.3 | UNKNOWN | Calculated Risk | 2025-01-14T13:12:00Z | 1458 | VERIFIED_PRE_RELEASE |
| H YoY | 2.8 | FactSet | FactSet Insight | date 2025-01-14 | — | PRE_RELEASE_DATE_ONLY |
| C YoY | 3.3 | FactSet | FactSet Insight | date 2025-01-14 | — | PRE_RELEASE_DATE_ONLY |
| H/C MoM+YoY | 0.3 / 2.8 / 0.2 / 3.3 | FactSet | Morningstar | date 2025-01-13 | — | PRE_RELEASE_DATE_ONLY |
| H/C MoM+YoY | 0.3 / 2.9 / 0.2 / 3.3 | unnamed n=38 | FinancialJuice | date 2025-01-13 | — | PRE_RELEASE_DATE_ONLY |

QA difference (do not trade): vs CR/FJ H MoM, 0.4 − 0.3 = **+0.1**. vs FactSet H YoY, 2.9 − 2.8 = **+0.1**. vs FJ H YoY, 2.9 − 2.9 = **0**.

### 2. CPI Apr 2025 — release 2025-05-13T12:30:00Z

Stage 1: 0.2 / 2.3 / 0.2 / 2.8

| Indicator | Candidate | Provider | Publisher | Pub time UTC | Lead (min) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| H MoM | 0.3 | UNKNOWN | FinancialJuice | date 2025-05-12 | — | PRE_RELEASE_DATE_ONLY |
| H YoY | 2.4 | UNKNOWN | FinancialJuice | date 2025-05-12 | — | PRE_RELEASE_DATE_ONLY |
| C MoM | 0.3 | UNKNOWN | FinancialJuice | date 2025-05-12 | — | PRE_RELEASE_DATE_ONLY |
| C YoY | 2.8 | UNKNOWN | FinancialJuice | date 2025-05-12 | — | PRE_RELEASE_DATE_ONLY |
| H YoY | — | FactSet | FactSet Insight | — | — | NOT_FOUND |

QA difference vs FJ H MoM: 0.2 − 0.3 = **−0.1**. No verified-clock consensus.

### 3. CPI Aug 2025 — release 2025-09-11T12:30:00Z

Stage 1: 0.4 / 2.9 / 0.3 / 3.1

| Indicator | Candidate | Provider | Publisher | Pub time UTC | Lead (min) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| H/C MoM+YoY | 0.3 / 2.9 / 0.3 / 3.1 | Reuters | Reuters (PPI article) | dateline Sept 10 | — | PRE_RELEASE_DATE_ONLY |
| H/C YoY | 2.9 / 3.1 | FactSet | FactSet Insight | date 2025-09-10 | — | PRE_RELEASE_DATE_ONLY |
| H/C MoM+YoY | 0.3 / 2.9 / 0.3 / 3.1 | FactSet | Morningstar | date 2025-09-09 | — | PRE_RELEASE_DATE_ONLY |

QA difference vs Reuters/FactSet H MoM: 0.4 − 0.3 = **+0.1**. Reuters and FactSet **agree** on this event. Still no clock.

### 4. Employment Dec 2024 — release 2025-01-10T13:30:00Z

Stage 1: NFP 256000 / UE 4.1 / AHE 0.3 / 3.9

| Indicator | Candidate | Provider | Publisher | Pub time UTC | Lead (min) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| NFP | 153000 | FactSet n=19 | FactSet Insight | date 2025-01-09 | — | PRE_RELEASE_DATE_ONLY |
| UE | 4.2 | FactSet n=17 | FactSet Insight | date 2025-01-09 | — | PRE_RELEASE_DATE_ONLY |
| NFP | 160000 | unnamed n=459 | FinancialJuice | date 2025-01-07 | — | PRE_RELEASE_DATE_ONLY |
| NFP | 165000 | unnamed | FinancialJuice morning | date 2025-01-10 | — | PRE_RELEASE_DATE_ONLY |
| UE | 4.2 | unnamed | FinancialJuice | dates 01-07 and 01-10 | — | PRE_RELEASE_DATE_ONLY |
| AHE YoY | 4.0 | unnamed | FinancialJuice morning | date 2025-01-10 | — | PRE_RELEASE_DATE_ONLY |

QA difference vs FactSet NFP: 256000 − 153000 = **+103000**. vs FJ 160k = **+96000**. vs FJ 165k = **+91000**. No verified-clock consensus.

### 5. Employment May 2025 — release 2025-06-06T12:30:00Z

Stage 1: NFP 139000 / UE 4.2 / AHE 0.4 / 3.9

| Indicator | Candidate | Provider | Publisher | Pub time UTC | Lead (min) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| NFP | 130000 | Reuters | WTAQ reprint | 2025-06-06T05:38:00Z | 412 | VERIFIED_PRE_RELEASE |
| UE | 4.2 | Reuters | WTAQ reprint | 2025-06-06T05:38:00Z | 412 | VERIFIED_PRE_RELEASE |
| AHE MoM | 0.3 | Reuters | WTAQ reprint | 2025-06-06T05:38:00Z | 412 | VERIFIED_PRE_RELEASE |
| AHE YoY | 3.7 | Reuters | WTAQ reprint | 2025-06-06T05:38:00Z | 412 | VERIFIED_PRE_RELEASE |
| NFP | 130000 | FactSet n=11 | FactSet Insight | date 2025-06-05 | — | PRE_RELEASE_DATE_ONLY |
| UE | 4.2 | FactSet n=11 | FactSet Insight | date 2025-06-05 | — | PRE_RELEASE_DATE_ONLY |

QA difference vs Reuters NFP: 139000 − 130000 = **+9000**. Reuters and FactSet **agree** on 130000.

### 6. Employment Sep 2025 — release 2025-11-20T13:30:00Z (lapse delay)

Stage 1: NFP 119000 / UE 4.4 / AHE 0.2 / 3.8

| Indicator | Candidate | Provider | Publisher | Pub time UTC | Lead (min) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| NFP | 50000 | FactSet | Euronews (AP) | 2025-11-20T11:54:00Z | 96 | VERIFIED_PRE_RELEASE |
| UE | 4.3 | FactSet | Euronews (AP) | 2025-11-20T11:54:00Z | 96 | VERIFIED_PRE_RELEASE |
| NFP | 50000 | FactSet n=19 | FactSet Insight | date 2025-10-02 | — | PRE_RELEASE_DATE_ONLY |
| UE | 4.3 | FactSet n=19 | FactSet Insight | date 2025-10-02 | — | PRE_RELEASE_DATE_ONLY |

QA difference vs FactSet NFP: 119000 − 50000 = **+69000**. AHE consensus was not recovered.

---

## PRIMARY QUESTION

Can we construct `surprise = official_BLS_first_print - pre_release_consensus` without look-ahead?

**For a verified-clock, provider-labelled series spanning all 2025 CPI and Employment events: not from the free public web.**

**For an experimental date-only FactSet (and occasional Reuters reprint) panel: maybe later, labelled as date-only, never averaged across providers, and never treated as equivalent to a Reuters poll vintage.**

The six-event pilot is enough to answer that. It is not enough to justify scaling collection.

---

## FINAL QUESTIONS

PILOT EVENTS INVESTIGATED: **6** (3 CPI, 3 Employment/NFP)

PILOT EVENTS WITH VERIFIED PRE-RELEASE CONSENSUS: **3**

CPI VERIFIED: **1** (`CPI_2024-12_2025-01-15`, unnamed consensus via Calculated Risk)

EMPLOYMENT/NFP VERIFIED: **2** (`EMPLOYMENT_SITUATION_2025-05_2025-06-06` Reuters via WTAQ; `EMPLOYMENT_SITUATION_2025-09_2025-11-20` FactSet via Euronews/AP)

REUTERS USABLE: **PARTIAL**

OTHER FREE SOURCES USABLE: **PARTIAL**

PUBLICATION TIMES SUFFICIENT TO PREVENT LOOK-AHEAD: **PARTIAL**

ENOUGH EVIDENCE TO SCALE TO ALL 2025 EVENTS: **NO**

PAID DATA REQUIRED AT THIS STAGE: **UNDETERMINED**

PRODUCTION CODE CHANGED: **NO**

LIVE STRATEGY CHANGED: **NO**

OANDA ORDERS SENT: **NO**

DOCKER RESTARTED: **NO**
