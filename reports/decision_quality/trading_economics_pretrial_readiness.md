# Trading Economics pretrial readiness

**Scope:** Research infrastructure only. Downloader, validator, tests, and this report.  
**Not included:** trial purchase, authenticated download, production edits, live FX join, surprise backtest.

Documentation checked: **2026-09-23**.

---

## OFFICIAL API SOURCES

| Source | URL | Date checked |
| --- | --- | --- |
| Docs home | https://docs.tradingeconomics.com/ | 2026-09-23 |
| Get started / auth | https://docs.tradingeconomics.com/get_started/ | 2026-09-23 |
| Calendar by country | https://docs.tradingeconomics.com/economic_calendar/country/ | 2026-09-23 |
| Calendar by ticker | https://docs.tradingeconomics.com/economic_calendar/ticker/ | 2026-09-23 |
| Calendar snapshot | https://docs.tradingeconomics.com/economic_calendar/snapshot/ | 2026-09-23 |
| Calendar response fields | https://docs.tradingeconomics.com/economic_calendar/schema/ | 2026-09-23 |
| Calendar “Point-in-Time” page | https://docs.tradingeconomics.com/economic_calendar/point-in-time/ | 2026-09-23 |
| Calendar streaming field notes | https://docs.tradingeconomics.com/economic_calendar/streaming/ | 2026-09-23 |
| API changelog | https://docs.tradingeconomics.com/change_log/ | 2026-09-23 |
| MCP tool list | https://docs.tradingeconomics.com/mcp/tools/ | 2026-09-23 |
| API pricing / trial caps | https://tradingeconomics.com/api/pricing.aspx | 2026-09-23 |
| Official Python client | https://github.com/tradingeconomics/tradingeconomics-python | 2026-09-23 |
| Client `calendar.py` (main) | https://raw.githubusercontent.com/tradingeconomics/tradingeconomics-python/main/tradingeconomics/calendar.py | 2026-09-23 |

No undocumented path was implemented. The official Python package is **not** a runtime dependency; this harness calls the documented REST URLs directly so dry-run, redaction, and immutable storage stay under our control. Client methods map as `te.getCalendarData(country=..., category=..., initDate=..., endDate=..., values=True)`.

---

## ENDPOINTS

Host: `https://api.tradingeconomics.com`  
Formats (`f=`): `json`, `csv` (HTML default). Optional `values=true` adds numeric `ActualValue` / `ForecastValue` / `PreviousValue` / `TEForecastValue` (JSON only; changelog 2023-07).

Documented calendar methods used or reserved:

| Purpose | Documented path |
| --- | --- |
| Country + indicator + date range (historical) | `/calendar/country/{countries}/indicator/{indicators}/{initDate}/{endDate}` |
| Country + group + date range | `/calendar/country/{country}/group/{group}/{start}/{end}` |
| Country + event + date range | `/calendar/country/{country}/event/{event}/{start}/{end}` |
| Ticker + date range | `/calendar/ticker/{ticker}/{start}/{end}` |
| Current snapshot | `/calendar` |
| By calendar id | `/calendar/calendarid/{id}` |
| Event name list | `/calendar/events/country/{country}` |
| Recent updates | `/calendar/updates` |

Filters documented on those pages: country, indicator/category, event, ticker, group, date range (`yyyy-MM-dd` or `yyyy-mm-dd HH:mm`), importance 1–3.

**Initial research targets (first-sample slugs):**

| Family | Documented selector | Why this slug |
| --- | --- | --- |
| US CPI | country `united states` + indicator `inflation rate` | Official country page and MCP `get_calendar_by_indicator` example |
| US NFP / Employment | country `united states` + indicator `non farm payrolls` | Schema example URL `/united-states/non-farm-payrolls`; space form matches documented `initial jobless claims` |
| FOMC / Fed rate | country `united states` + group `interest rate` | Official group list on the country calendar page |

Local name hints (CPI / NFP / FOMC) run **after** download. They do not invent extra HTTP paths. If a slug returns empty or HTTP error, that is recorded; we do not silently try unofficial aliases.

---

## POINT-IN-TIME ENDPOINT

The page titled “Economic Calendar Point-in-Time” documents this URL:

`https://api.tradingeconomics.com/calendar/country/{countries}/indicator/{indicators}/{initDate}/{endDate}`

That is the **ordinary historical calendar** path. The official Python client has **no** separate `getCalendarPointInTime` function; it uses `getCalendarData(..., initDate, endDate)`. MCP lists a tool named `get_calendar_point_in_time`, but the documented HTTP example is the same date-range calendar.

**There is no documented distinct REST path** such as `/calendar/point-in-time/{asof}`.

The marketing text says rows appear “exactly as they appeared on a specific date.” The `initDate`/`endDate` parameters are the **event scheduled-date window**, not a proven as-of vintage clock. The published example (2016 US jobless claims) shows `Forecast`, `Actual`, and `LastUpdate` equal to the release `Date`. That example does **not** prove a pre-release consensus vintage.

This harness therefore treats “PIT” as a **claim to be tested on returned records**, not as a property of the URL name.

---

## AVAILABLE FIELDS

Official schema (`docs.tradingeconomics.com/economic_calendar/schema/`):

| Official field | Maps to | Notes |
| --- | --- | --- |
| CalendarId / CalendarID | `event_id` | Unique TE event id |
| Country | `country` | |
| Category | `category` | |
| Event | `event` | |
| Date | `scheduled_time_raw` | Documented as **UTC** |
| Actual | `actual` | Schema: **“Latest released value”** |
| Forecast | `forecast_consensus` | Schema: consensus of a representative group of economists |
| TEForecast | `te_forecast` | Schema: **Trading Economics’ own projection** |
| Previous | `previous` | Schema: previous **after revision if applicable** |
| Revised | `revised` | Schema: previous-release value **before** revision |
| Importance | `importance` | 1 low / 2 medium / 3 high |
| LastUpdate | `last_update_raw` | Schema: most recent **update or insertion** |
| Ticker / Symbol | `ticker` / `symbol` | |
| Source / SourceURL | `source` / `source_url` | |
| ForecastValue / TEForecastValue / … | numeric twins when `values=true` | Kept separate |

`Forecast` and `TEForecast` are **never merged**. Missing `Forecast` stays missing.

Streaming docs also state `date` is UTC and `forecast` is the average among economists; `teforecast` is TE’s own projection.

---

## AUTHENTICATION

From Get Started (2026-09-23):

- Subscribe and obtain a key at developer.tradingeconomics.com
- Pass the key as query `c` / `client`, **or** as an `Authorization` HTTP header
- This harness uses the **header only** so planned URLs and metadata never contain the key
- Environment variable: `TRADING_ECONOMICS_API_KEY`
- Template (empty): `forex_bot/decision_quality/trading_economics/env.template`
- No key was written to `.env` or source control

---

## REQUEST LIMITS

| Item | Documented? | Value |
| --- | --- | --- |
| Trial request cap | **Yes** — pricing page | **100 requests** |
| Trial data-point cap | **Yes** — pricing page | **100000 data points** |
| Trial commercial terms | **Yes** — pricing page | Fee not refundable; unused trial auto-charges if not cancelled |
| Calendar rows per response | **Partial** | Changelog (2021-07 / 2021-09): “new limits on rows by role”; “top limit rows by calendar role.” **Number not published.** |
| Pagination cursor / page param for calendar | **Not documented** | Absent from calendar docs |
| Date formats | **Yes** | `yyyy-MM-dd` and `yyyy-mm-dd HH:mm` |
| Guest `guest:guest` | Not in current Get Started | Treated as discontinued; not used |

Uncertainty is explicit: a long date range **may** truncate without a documented next-page token. The first live sample must check whether `record_count` looks complete versus expected monthly/FOMC cadence.

---

## REQUEST-EFFICIENCY PLAN

Do **not** request one event at a time. Prefer one date-range call per family.

Lower bound for US CPI + NFP + FOMC (three documented range URLs):

| Horizon | Window (example if run 2026-09-23) | Planned requests | Upper bound |
| --- | --- | --- | --- |
| 3 months | ~2026-06-01 → 2026-09-23 | **3** | UNKNOWN (role row limit) |
| 1 year | ~2025-09-01 → 2026-09-23 | **3** | UNKNOWN |
| 3 years | ~2023-09-01 → 2026-09-23 | **3** | UNKNOWN |
| 5 years | ~2021-09-01 → 2026-09-23 | **3** | UNKNOWN |
| **sample (first key run)** | **~18 months** | **3** | UNKNOWN |

Trial budget: 3 requests is 3% of the documented 100-request trial cap. Even a later 5-year pull stays at 3 requests **if** the API returns the full window in one body. If a body is truncated, split the window (still far below 100 unless the unpublished page size is tiny).

A single US-wide `/calendar/country/united%20states/{start}/{end}` call would be 1 request but would pull every US event (~1600 global events/month per docs home). That is more likely to hit the unpublished row cap and is **not** the first-sample plan.

---

## NORMALIZED SCHEMA

```
provider
event_id
country
category
event
scheduled_time          # UTC conversion report lives beside scheduled_time_raw
actual
forecast_consensus      # Forecast only
te_forecast             # TEForecast only
previous
revised
importance
last_update
ticker
source
retrieved_at
```

Plus preserved raw strings, optional numeric `*_value` fields, `symbol`, `reference`, `unit`, `date_span`, `raw_sha256`. Missing values stay null. Raw JSON is stored first under `data/research/trading_economics/raw/` with metadata:

- retrieval UTC
- method / endpoint / parameters (no key)
- HTTP status
- record count
- SHA256
- `api_key_stored: false`

Existing raw files are never overwritten.

---

## PIT VALIDATION RULES

A row is **not** point-in-time safe because the page is named Point-in-Time.

| ID | Question | Pass rule | Default on ordinary historical row |
| --- | --- | --- | --- |
| A | Was consensus known before release? | `Forecast` present **and** (Actual empty with `LastUpdate` < `Date`, or an explicit earlier snapshot). `TEForecast` is never a substitute. | **INSUFFICIENT** — Forecast without a pre-release clock |
| B | Is Actual the first print? | Two snapshots of the same `CalendarId` with different `Actual` values, earliest kept. Schema says Actual is latest. | **INSUFFICIENT** |
| C | Is Previous as-known-at-time? | Need a vintage that predates a later Previous revision. Schema says Previous may already be revised; `Revised` is the pre-revision previous. | **INSUFFICIENT / FAIL** when Revised ≠ Previous |
| D | Does LastUpdate prove vintage? | Only if TE documents it as consensus-asof **and** payloads show LastUpdate < Date with Forecast set. Schema says update/insertion. | **INSUFFICIENT** |
| E | Does PIT differ from ordinary historical? | Compare two live payloads. Docs currently show the same URL. | **UNKNOWN** until authenticated compare |
| F | Multiple historical snapshots of one event? | Distinct retrievals or `/calendar/calendarid/{id}` vs range row differ. No documented as-of parameter. | **UNKNOWN** |
| G | Separate pre-release consensus / first print / later revision? | A and B both pass on the same `CalendarId`. | **INSUFFICIENT** |

`vintage_ok` is true only when A and B pass. Surprise is refused otherwise.

The ordinary 2016 jobless-claims fixture from the official PIT page **fails** these rules (as it should).

---

## SAMPLE DOWNLOAD PLAN

First authenticated run: **`--profile sample` only** (~18 months, 3 requests). Goal: validate the provider, not backtest.

Approximate row expectation if slugs match (not a request count): ~18 CPI-family months, ~18 NFP-family months, ~12 FOMC-family meetings, plus extra inflation/labour/rate events returned by the broad selectors. Local hints then mark CPI / NFP / FOMC-like names.

CLI refuses `--confirm` on `1y` / `3y` / `5y` until this sample is validated.

Dry-run (zero requests, no key required):

```
python -m forex_bot.decision_quality.trading_economics.download --dry-run --profile sample
```

---

## CROSS-PROVIDER COMPARISON PLAN

No Econoday file exists in this repository, so **no Econoday parser was written**.

Interface ready in `compare.py`:

- `ComparisonKey(country, category_family, reference_period, scheduled_utc)`
- `ProviderPrint` for TE vs Econoday consensus and first-print actual
- `empty_econoday_slot(...)` marks `MISSING_ECONODAY`

When a real Econoday sample arrives, map it onto `ProviderPrint` and compare `forecast_consensus` and `actual_first_print` only after each side’s vintage checks pass.

---

## KNOWN UNCERTAINTIES

1. Official PIT page = ordinary historical calendar URL. Distinct as-of semantics **unproven**.
2. Calendar page size / role row limit **unpublished**.
3. Exact live indicator strings for “Employment Situation” vs “Non Farm Payrolls”, and Fed “Interest Rate Decision” vs group members, are **not confirmed** until the sample returns.
4. `Date` is documented UTC but examples are naive ISO strings. Conversion flags `naive_datetime_no_offset` and assumes the documented UTC claim.
5. Whether `/calendar/calendarid/{id}` can return an old vintage, or only today’s row, is **unknown**.
6. Trial 100-request cap is documented; remaining allowance on a future key is unknown.
7. No Econoday schema on disk.

---

## TEST RESULTS

`tests/test_trading_economics_pretrial.py` uses local fixtures only. **20 passed** (plus existing broker-isolation check).

Covered:

- API key never printed or stored in metadata
- dry-run performs zero requests (`requests.get` patched to explode)
- Forecast vs TEForecast stay separate
- missing Forecast does not become TEForecast
- timestamp conversion (Z, naive UTC-claim, missing, malformed)
- duplicate `CalendarId`
- raw file immutability
- normalization
- surprise rejected when vintage fails
- surprise accepted only on a two-plus-snapshot fixture that passes A and B
- HTTP 401, 429 (+ Retry-After), 500, malformed body
- isolation: package does not import broker/bot_loop

---

## GATE ANSWERS

CAN THE CODE BE RUN IN DRY-RUN WITHOUT CREDENTIALS?  
**YES**

REAL API CALLS MADE?  
**NO**

TRADING ECONOMICS CREDENTIAL PRESENT?  
**NO**

LIVE BOT CODE CHANGED?  
**NO**

OANDA ORDERS SENT?  
**NO**

DOCKER RESTARTED?  
**NO**

PRODUCTION CODE CHANGED: NO  
LIVE STRATEGY CHANGED: NO
