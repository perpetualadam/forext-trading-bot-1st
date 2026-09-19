# Quant V2 — FXMacroData free PIT consensus feasibility probe

VERDICT:
FXMACRODATA_UNSUITABLE

NEXT ACTION:
PAID_VENDOR_SAMPLE_REQUEST_JUSTIFIED

**Status:** COMPLETE — read-only provenance probe. No purchase. No trial. No bulk download. No surprise study. No FX join. No production change.

Existing frozen sample `quant_v2_pit_consensus_frozen_sample.json` (S01–S18) was **not** modified.

---

## Plain-English summary

- **What did we actually get for free?** Coverage metadata, the USD data catalogue, the USD calendar, and the last 90 days of USD **announcement** rows (clocks, official source URLs, latest actuals, some revision arrays). **No forecast values.**
- **Did we see a real consensus number?** **No.** Every `/v1/predictions/usd/...` request returned **401 `api_key_required`**.
- **Did we prove it existed before release?** **No.** There was no prediction value and no prediction as-of timestamp to test.
- **Can it be tied to the exact announcement?** **Announcement IDs yes** (`usd_inflation_2026-08-31` form). Predictions are documented to use the same ID, but we could not inspect a prediction row.
- **Can we safely calculate surprise yet?** **No.**
- **Can we use it prospectively?** We could snapshot **clocks/actuals** after release. We **cannot** freely snapshot pre-release consensus. A paid plan still does **not** create compiled event consensus for monthly CPI, NFP, or the FOMC policy-rate series.
- **Do we need to pay anyone yet?** **Not FXMacroData.** The remaining written sample request is still **Econoday or Bloomberg PIT**, who claim calendar-style event consensus. Do not start the FXMacroData 14-day trial for this purpose.

---

## Stage 1 — Documentation verification

Sources used:

| URL | Role |
| --- | --- |
| https://fxmacrodata.com/documentation/predictions | Prediction classes, coverage, provenance |
| https://fxmacrodata.com/documentation/quickstart | Auth, free-window claims |
| https://fxmacrodata.com/documentation/reference | Endpoint inventory |
| https://fxmacrodata.com/documentation/announcement-endpoint | Revision selectors, 90-day freemium |
| https://fxmacrodata.com/documentation/data-quality | `point_in_time_safe` |
| https://fxmacrodata.com/features/point-in-time-history | Known-at marketing page |
| https://fxmacrodata.com/articles/forecasting-macro-releases-with-predictions-api | Older article (partly stale) |
| https://api.fxmacrodata.com/v1/predictions/coverage and `/coverage/usd` | Live no-key catalogue |

| Claim | Classification |
| --- | --- |
| Distinct prediction classes including compiled consensus, surveys, model, FXMacroData | **VERIFIED_DOCUMENTATION** (live coverage catalogue repeats the taxonomy) |
| `compiled_consensus` / `forecaster_survey` named | **VERIFIED_DOCUMENTATION** |
| Generated/model predictions labelled `fxmacrodata` / `model_nowcast` and must not be called consensus | **VERIFIED_DOCUMENTATION** |
| Stable `announcement_id` | **VERIFIED_DOCUMENTATION** and **verified on free announcement rows** |
| Historical / recent predictions | **AMBIGUOUS** — docs conflict (quickstart: USD free 90 or 365 days; predictions page: values need a plan on every currency). **Live API: 401** |
| Coverage endpoints, no key, no values | **VERIFIED_DOCUMENTATION** and live **200** |
| Point-in-time semantics | **AMBIGUOUS** — announcements have `announcement_datetime` and `data_quality.point_in_time_safe`; sampled announcement payloads set that flag **false** |
| Prediction as-of / `generated_at` / provenance | **VERIFIED_DOCUMENTATION** as fields; **NOT_FOUND** on any free prediction row |
| Revisions `latest` / `first` / `final` / `all` | **VERIFIED_DOCUMENTATION**; default live rows used `latest` |
| First-print actuals | **AMBIGUOUS** — selector claimed; default NFP `val` was **not** the `is_first_release` revision |
| Previous values | **VERIFIED_DOCUMENTATION** / present on some announcement rows; semantics **AMBIGUOUS** |
| USD coverage | **VERIFIED_DOCUMENTATION** and live catalogue |
| Authentication / free no-key access | **VERIFIED_DOCUMENTATION** with **internal contradiction**; live: coverage+USD announcements free; predictions paid |
| Rate limits | **VERIFIED_DOCUMENTATION** (100 no-key USD requests/day; 15-minute delay) |

Do not treat the quickstart “USD predictions are free” sentence as live behavior.

---

## Stage 2 — Relevant endpoints

| Endpoint | Auth | Parameters used | Documented depth / limit |
| --- | --- | --- | --- |
| `GET /v1/predictions/coverage` | None | — | Catalogue only |
| `GET /v1/predictions/coverage/usd` | None | — | Catalogue only |
| `GET /v1/data_catalogue/usd` | None | — | Indicator slugs |
| `GET /v1/calendar/usd` | None | — | Upcoming/recent schedule |
| `GET /v1/announcements/usd/{indicator}` | None for recent USD | `limit=3` | Freemium **90 days**; key for history |
| `GET /v1/predictions/usd/{indicator}` | **Key required** (live 401) | `prediction_class`, `limit=3` | Values locked; 401 still returns coverage |

Paid/auth endpoints were **not** retried after 401.

---

## Stage 3 — Free coverage probe

Live `/v1/predictions/coverage/usd` (200, no key):

| Indicator | `has_consensus_source` | Classes present | Compiled consensus |
| --- | --- | --- | --- |
| `inflation` | true (Philly Fed SPF = `forecaster_survey`) | model_nowcast, fxmacrodata, institutional_projection, forecaster_survey | **Absent** |
| `non_farm_payrolls` | **false** | fxmacrodata only | **Absent** |
| `policy_rate` | **false** | market_implied, central_bank_projection, fxmacrodata | **Absent** |
| `policy_rate_midpoint` | true (NY Fed SME) | fxmacrodata, forecaster_survey | Absent; survey claimed from 2023-07-26 |

Access object: `coverage_requires_key=false`, `values_require_key=true`. “No subscription adds a source that is not listed here.”

Claimed archive floors (coverage / 401 `verified_history`, **not** PIT-verified values):

- Cleveland Fed CPI nowcast: 2013-08-31, every monthly release
- Philly Fed SPF NFP: quarterly since 2003-11-24; **no per-release monthly consensus**
- Atlanta Fed market-implied policy: sparse from 2023-09-20
- NY Fed SME policy midpoint: most FOMC meetings from 2023-07-26

No prediction history was downloaded.

---

## Stage 4 — Frozen PIT standard

Frozen in `reports/decision_quality/quant_v2_fxmacrodata_pit_standard.json` **before** prediction-value calls.

Required: prediction value, type, publisher, announcement identity, and `prediction_asof < official_release_time` (or equally strong proof). A field named forecast is not enough. `fxmacrodata` / nowcast is not consensus.

---

## Stage 5 — Small recent USD sample

Selection rule frozen first: most recent completed USD announcement per INFLATION / EMPLOYMENT / CENTRAL_BANK_DECISION from no-key `announcements?limit=3`. Not chosen by later FX move.

Persisted in `quant_v2_fxmacrodata_frozen_recent_usd_ids.json` **before** prediction calls:

| Category | announcement_id | Official-style clock |
| --- | --- | --- |
| INFLATION | `usd_inflation_2026-08-31` | 2026-09-11 08:30 America/New_York |
| EMPLOYMENT | `usd_non_farm_payrolls_2026-08-31` | 2026-09-04 08:30 America/New_York |
| CENTRAL_BANK_DECISION | `usd_policy_rate_2026-09-16` | 2026-09-16 14:00 America/New_York |

These September 2026 events were inspected during this probe. They are **DEVELOPMENT**, not a pristine holdout.

---

## Stage 6 — Prediction type audit

No prediction **values** were returned. From coverage + 401 `availability`:

| Target | If a paid row existed, documented type | Probe class |
| --- | --- | --- |
| Monthly CPI YoY | Cleveland nowcast / OECD / FXMacroData blended; SPF is quarterly `official_forecasts` | MODEL_GENERATED / OTHER / FORECASTER_SURVEY (wrong cadence) |
| Monthly NFP | FXMacroData blended only in `data[]` | MODEL_GENERATED |
| FOMC `policy_rate` | Atlanta market-implied / FOMC SEP / blended | OTHER / CENTRAL_BANK_FORECAST / MODEL_GENERATED |
| FOMC midpoint | NY Fed SME `forecaster_survey` (paid) | FORECASTER_SURVEY (unseen) |

`compiled_consensus` for the three sampled series: **no_source_for_pair**.

---

## Stage 7 — PIT timestamp audit

| Event | Scheduled / planned | Vendor `announcement_datetime` | Prediction timestamp | Class |
| --- | --- | --- | --- | --- |
| CPI Aug 2026 | 2026-09-11 12:30 UTC | 1789129800 = same | **None** (401) | **UNKNOWN** |
| NFP Aug 2026 | 2026-09-04 12:30 UTC | 1788525000 = same | **None** | **UNKNOWN** |
| FOMC 2026-09-16 | 2026-09-16 18:00 UTC | 1789581600 = same | **None** | **UNKNOWN** |

Announcement payload notes:

- `publication_time_status=unverified`, precision unknown
- `data_quality.point_in_time_safe=false` (`unverified_vintage_count` > 0)
- `collected_at` is fetch time, sometimes minutes after the planned clock (CPI +6.7s; FOMC first fetch +4m10s with a **wrong** 3.75 before later 4.00)
- A post-release collect timestamp is **not** a pre-release consensus vintage

---

## Stage 8 — Announcement identity

Relationship is `announcement_id = {currency}_{indicator}_{reference_period_date}`, not the release date.

- CPI released 2026-09-11 → `usd_inflation_2026-08-31`
- NFP released 2026-09-04 → `usd_non_farm_payrolls_2026-08-31`
- FOMC 2026-09-16 → `usd_policy_rate_2026-09-16`

This is the correct “prediction → announcement → exact release” shape **if** predictions use the same ID. That join was not observed on a prediction row.

---

## Stage 9 — Official clock cross-check

Compared to Experiment D official clocks (not FX outcomes):

| Official D id | Official UTC | Vendor row | Match |
| --- | --- | --- | --- |
| S03 CPI July 2026 | 2026-08-12T12:30:00 | `usd_inflation_2026-07-31` 1786537800 | **Yes** |
| S06 Employment July 2026 | 2026-08-07T12:30:00 | `usd_non_farm_payrolls_2026-07-31` 1786105800 | **Yes** |
| S09 FOMC 2026-07-29 | 2026-07-29T18:00:00 | `usd_policy_rate_2026-07-29` 1785348000 | **Yes** |

Vendor source URLs point at official archives (`bls.gov/news.release/archives/cpi_09112026.htm`, `empsit_09042026.htm`, Fed `monetary20260916a.htm`). The Fed HTML fetch timed out here; the path matches the official press-release pattern and the 14:00 ET clock matches Experiment D’s FOMC rule.

No lapse-delay or BoC 09:45 issue appears in this USD sample.

---

## Stage 10 — Actual / revision semantics

Default announcement filter is **`revisions=latest`**.

NFP July 2026 (`usd_non_farm_payrolls_2026-07-31`):

- latest `val` = **158,913,000**
- revision flagged `is_first_release=true` = **158,858,000**

So the headline actual is **LATEST_REVISED**, not first print. First print is only in `revisions[]` when that flag is present.

CPI sampled revisions all showed 3.4 with `is_first_release=false`.

FOMC 2026-09-16: first stored snapshot was 3.75, later 4.0, both `is_first_release=false`. That looks like **capture error**, not an official revision.

`previous_value` is present on some rows. Whether it is previous-as-known-before-release is **UNKNOWN**.

Classification: actuals **BOTH_SEPARATELY possible** if `revisions=first` / `is_first_release` is trusted; **default path is LATEST_REVISED**. Previous: **UNKNOWN**.

---

## Stage 11 — Surprise feasibility

Desired later: `first_print_actual - consensus_pre_release`. **Not calculated.**

| Requirement | Status |
| --- | --- |
| Exact announcement identity | **PARTIAL** (IDs/clocks yes; prediction join unseen) |
| Genuine consensus prediction | **FAILED** for compiled event consensus on CPI/NFP/FOMC `policy_rate` |
| Prediction known before release | **FAILED** (no value, no as-of) |
| First-print actual | **PARTIAL** (NFP first vs latest visible; default is latest) |
| Compatible units | **UNKNOWN** (no consensus value) |
| Correct reference period | **PARTIAL** (announcement `date` is reference month) |
| Revisions separated | **PARTIAL** (possible; default leaks later NFP) |

---

## Stage 12 — Free access boundary

Works without payment:

- coverage, coverage/usd, data_catalogue/usd, calendar/usd
- USD announcements in the **last 90 days** (`freemium_window.max_days=90`, cutoff 2026-06-21 on this retrieval)
- 401 bodies that list sources and `no_source_for_pair` / `values_require_key`

Requires authentication / payment (live 401 + docs):

- all prediction **values**, USD included
- announcement history older than 90 days
- real-time (docs: 15-minute delay without key)
- non-USD

A 14-day trial is advertised. It was **not** started. It requires a plan.

---

## Stage 13 — Historical depth

| Series | COVERAGE CLAIMED | PIT DATA ACTUALLY VERIFIED |
| --- | --- | --- |
| US CPI | Cleveland nowcast monthly from 2013; SPF quarterly; no compiled monthly consensus | **None** (401) |
| US Employment / NFP | SPF quarterly from 2003; **no monthly consensus** | **None** |
| FOMC | Market-implied sparse from 2023; NY Fed SME midpoint from 2023-07 (paid); SEP | **None** |

---

## Stage 14 — Existing frozen S01–S09

S01–S18 file untouched.

| Sample | Result |
| --- | --- |
| S03, S06, S09 | Announcement clocks **COVERAGE_APPEARS_AVAILABLE** inside the free 90-day window (already in `limit=3` payloads) |
| S01, S02, S04, S05, S07, S08 | Free announcements **COVERAGE_NOT_AVAILABLE** (before 2026-06-21 cutoff) |
| S01–S09 compiled consensus values | **COVERAGE_NOT_AVAILABLE** (`no_source_for_pair`) |
| S01–S09 any prediction values | **UNKNOWN** without a key; **not fetched** |

---

## Stage 15 — Prospective collection (design only)

Without a key, the research system **cannot** periodically capture genuine consensus snapshots. Prediction values are locked.

What could be stored later, **if separately authorized and licensed**:

- raw response bytes
- retrieval timestamp UTC
- announcement ID
- scheduled / `official_planned_release_datetime`
- prediction value / class / publisher
- prediction as-of / `generated_at` / provenance
- checksum
- source endpoint

Not implemented. No scheduler. No bot change.

Free prospective capture of **post-release clocks** is possible but does not solve surprise.

---

## Stage 16 — Holdout

2025-09 through 2026-08 remains DEVELOPMENT / DISCOVERY. The September 2026 CPI, NFP, and FOMC rows inspected here are also development. They are **not** a pristine holdout.

---

## Stage 17 — Provider quality summary

| Category | Grade |
| --- | --- |
| CONSENSUS SEMANTICS | **PARTIAL** taxonomy is clear; required compiled event consensus **absent** for CPI/NFP/FOMC `policy_rate` |
| PIT TIMESTAMP QUALITY | **PARTIAL** for announcement clocks; **UNKNOWN** for predictions; `point_in_time_safe=false` on sampled actuals |
| ANNOUNCEMENT ID QUALITY | **VERIFIED GOOD** on free announcement rows |
| CLOCK QUALITY | **VERIFIED GOOD** vs Experiment D S03/S06/S09 |
| FIRST-PRINT ACTUAL QUALITY | **PARTIAL** (selector claimed; default is latest; NFP first ≠ latest) |
| REVISION HANDLING | **PARTIAL** |
| USD CPI COVERAGE | **PARTIAL** (clocks/actuals yes; compiled consensus no) |
| USD EMPLOYMENT COVERAGE | **UNSUITABLE** for monthly consensus |
| FOMC COVERAGE | **PARTIAL** (clocks yes; compiled consensus no; paid SME unseen) |
| FREE ACCESS | **PARTIAL** (metadata + recent actuals; no forecast values) |
| HISTORICAL DEPTH | **UNKNOWN** for PIT consensus; claimed nowcast/SPF only |
| PROSPECTIVE COLLECTION VALUE | **UNSUITABLE** for free consensus snapshots |
| LEAKAGE RISK | **PARTIAL** (latest actual default; capture errors; model labelled as forecast) |

---

## Stage 18 — Final questions

1. Does FXMacroData distinguish consensus from generated forecasts? **Yes, in documentation and the free coverage catalogue.**
2. Is `compiled_consensus` available for relevant USD events? **No** for monthly CPI, NFP, and `policy_rate`.
3. Can a prediction be tied to an exact announcement ID? **Documented yes; not observed on a prediction row.**
4. Does the prediction have a meaningful pre-release timestamp? **Not seen.**
5. Can we prove the prediction existed before release? **No.**
6. Are recent USD prediction values legitimately accessible for free? **No. 401.**
7. Is CPI covered? **Clocks/actuals yes. Compiled consensus no. SPF quarterly only.**
8. Is Employment/NFP covered? **Clocks/actuals yes. No official monthly consensus source.**
9. Are FOMC decisions covered? **Clocks/actuals yes. No compiled consensus. Paid NY Fed SME on midpoint unseen.**
10. How far back is coverage claimed? Nowcast 2013; SPF NFP 2003 quarterly; SME 2023. Free announcements 90 days.
11. Is historical PIT coverage verified rather than claimed? **No.**
12. Are first-print actuals available? **Partially, via revision flags / a `revisions=first` selector. Default is latest.**
13. Are revisions separated? **Sometimes in `revisions[]`. Default headline is latest.**
14. Could a causal surprise eventually be reconstructed? **Not from free FXMacroData, and not from compiled consensus they do not carry for these events.**
15. Could we begin collecting trustworthy future PIT snapshots ourselves? **Not of consensus, without a paid plan. Paying them still would not add compiled CPI/NFP/FOMC consensus.**
16. Does FXMacroData appear capable of covering frozen S01–S09? **Clocks for the latest three only on the free window. Compiled consensus: no.**
17. Is there any reason to pay another provider yet? **Only the already-specified written Econoday/Bloomberg sample, not an FXMacroData trial.**

---

## Stage 19 — Verdict

# FXMACRODATA_UNSUITABLE

Free FXMacroData does not supply consensus values. The live coverage/401 contract says **no publisher they carry produces compiled event consensus** for US CPI, NFP, or the FOMC policy-rate series, and **a subscription does not add that source**. That cannot support the intended causal surprise research.

---

## Stage 20 — Next action

# PAID_VENDOR_SAMPLE_REQUEST_JUSTIFIED

This does **not** authorize purchase. It does **not** authorize an FXMacroData trial.

The sample request remains the prior PIT-audit request to **Econoday or Bloomberg**: written PIT extract of frozen S01–S09 with `consensus_asof ≤ scheduled clock`, first-print actual, previous-as-known, and separate revisions.

---

## Tests / stop

Helpers cover timestamp parsing, class labels, `prediction_asof < release`, NFP first vs latest, and raw-file immutability.

`python -m pytest -q --tb=line` → **429 passed / 0 failed / 0 skipped / 28.47s**.

No surprise backtest. No FX join. No training. No `_quant_stub_vote` change. No filters. No bot/Docker restart. No purchase. Stop for human review.
