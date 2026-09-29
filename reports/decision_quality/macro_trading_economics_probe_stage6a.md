# MACRO RESEARCH — TRADING ECONOMICS STAGE 6A
# AUTHENTICATED CALENDAR API CAPABILITY PROBE

One authorized Calendar GET. No retries. No scheduler activation.
`FORWARD_CONSENSUS_COLLECTION_ENABLED` remains false.
Windows task `ForexMacroProspectiveCollectDue` was not modified.

CREDENTIAL STATUS
-----------------
`TRADING_ECONOMICS_API_KEY` is configured in the local repository `.env`.
`.env` is gitignored. The value was never printed, committed, or written
into probe artifacts, reports, tests, or scheduler logs.
Auth method used: HTTP `Authorization` header (not query `c=`).

REQUEST
-------
Count before: 0. Count after: 1. Guard rejects request #2.
Documented URL (no key in URL):

`https://api.tradingeconomics.com/calendar/country/united%20states/2026-10-02/2026-10-02?f=json&values=true`

This is the documented country + closed date-range Calendar path for a
single US release day (pretrial readiness 2026-09-23). `f=json&values=true`
are query flags on the same GET.

HTTP result: **403 ACCESS_DENIED**
No second request was made.

API RESPONSE SCHEMA
-------------------
No calendar JSON rows were returned. Field names could not be inspected
from a live body. Documented schema (unchanged) remains:

CalendarId, Country, Category, Event, Date (UTC), Actual, Forecast
(economist consensus), TEForecast (TE proprietary), Previous, Revised,
Importance, LastUpdate, Ticker/Symbol, Source/SourceURL, optional
ForecastValue/TEForecastValue when `values=true`.

EMPLOYMENT SERIES
-----------------
From this authenticated response: none identifiable.

| series | found |
|---|---|
| nonfarm_payroll_change | NO |
| unemployment_rate | NO |
| average_hourly_earnings_mom | NO |
| average_hourly_earnings_yoy | NO |

ADP / claims / JOLTS were not used as substitutes.

CONSENSUS FIELDS
----------------
Not observed. Documented name: `Forecast` / `ForecastValue`.

TE FORECAST FIELDS
------------------
Not observed. Documented name: `TEForecast` / `TEForecastValue`.
These remain distinct in parser/tests. They were not merged.

POINT-IN-TIME CAPABILITY
------------------------
PIT_MECHANISM_IDENTIFIED: YES (docs page uses the ordinary historical
calendar country/indicator/date URL; no distinct `/calendar/point-in-time/{asof}`).
PIT_ACCESS_CONFIRMED: NOT_CONFIRMED (403; no vintage/as-of proof on this account).

TRIAL / QUOTA INFORMATION
-------------------------
No extra request was made for quota. Prior public pricing page (2026-09-23):
trial **100 requests** / **100000 data points**. Role row limit unpublished.
This probe consumed 1 of those requests.

ARTIFACT
--------
`data/research/macro/consensus_pit/prospective/probes/te_calendar_2026-10-02.sanitized.json`
SHA-256: `5eb58fb4713738708b28cca487a922afe6837af4e1288d29b7744b2b664af68a`
Credential present in artifact: NO
Did not enter `observations/observations.jsonl`.

ARCHIVAL PERMISSION
-------------------
NOT_CONFIRMED. No calendar payload was delivered. Technical 403 is not
a license grant. Local research retention of future TE JSON remains
unconfirmed against trial terms.

ADAPTER GAP
-----------
`TradingEconomicsAdapter.collect()` remains a production no-fetch stub.
Not approved. Not enabled. Remaining work after a successful later probe:
entitlement/path confirmation, authenticated GET with timeout, request
accounting, exact series mapping, Forecast vs TEForecast split, unit and
reference-period handling, observed_at_utc, artifact hash, fail-closed
validation. Do not enable the scheduler to call it.

SCHEDULER SAFETY
----------------
FORWARD_CONSENSUS_COLLECTION_ENABLED=false
trading_economics.enabled=false
automation_class is not APPROVED_AUTOMATION_READY
Official BLS adapter remains disabled
Windows task not edited. Expected scheduler TE requests: 0.

TEST RESULTS
------------
76 passed. Stage 6A 5, Stage 4 10, Stage 5 7, Stage 1 12, Stage 2 13,
Stage 3 15, consensus Stage 2 14. No test network calls.

NEXT STEP
---------
Do not promote Trading Economics. Investigate the 403 with Trading Economics
support or the trial dashboard (Calendar entitlement / key format) without
issuing another automated request from this recorder. Only a later explicit
activation stage may enable collection after a successful calendar response
and archival confirmation.
STOP.
