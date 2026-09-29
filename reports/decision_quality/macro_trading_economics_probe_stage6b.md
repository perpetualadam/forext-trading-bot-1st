# MACRO RESEARCH — TRADING ECONOMICS STAGE 6B
# CALENDAR AUTHENTICATION + ONE-REQUEST VALIDATION

At most one new Calendar GET after an offline audit of Stage 6A.
`FORWARD_CONSENSUS_COLLECTION_ENABLED` remains false.
Windows task `ForexMacroProspectiveCollectDue` was not modified.
Trading Economics was not promoted and was not enabled.

STAGE 6A REQUEST AUDIT
----------------------
Host `api.tradingeconomics.com` and output flag `f=json` matched the
documented Calendar host/format.

Stage 6A did not match the documented authentication or date-filtered
path supplied for Stage 6B:

- authentication: HTTP `Authorization` header, not `c` query parameter
- path: `/calendar/country/united%20states/2026-10-02/2026-10-02`
  instead of `/calendar/country/All/2026-10-02/2026-10-02`
- query names: `f`, `values` (no `c`; extra `values=true`)

Documented pattern match: NO.

STAGE 6B REQUEST
----------------
Probe-only correction. Production collector and source registry were
not changed. Constructed programmatically from `TRADING_ECONOMICS_API_KEY`.
The credential-bearing URL was not printed, logged, or stored.

- host: `api.tradingeconomics.com`
- path: `/calendar/country/All/2026-10-02/2026-10-02`
- query parameter names: `c`, `f`
- authentication: `c` query parameter
- headers: `Accept: application/json` only

New external Trading Economics requests: 1. Guard rejects request #2.
Total known probe requests: 2 (Stage 6A + Stage 6B).
Scheduler Trading Economics requests: 0.

HTTP result: **403 ACCESS_DENIED**
No retry. No fallback endpoint. No CalendarId follow-up.

CREDENTIAL STATUS
-----------------
Configured: YES. Exposed: NO. Present in artifacts: NO.
`.env` remains gitignored. Explicit leak scan of Stage 6B artifacts,
probe module, tests, and fixture: clean.

EMPLOYMENT SERIES
-----------------
No calendar JSON rows were returned. Local United States / 2026-10-02
filter therefore saw 0 events.

| series | found |
|---|---|
| nonfarm_payroll_change | NO |
| unemployment_rate | NO |
| average_hourly_earnings_mom | NO |
| average_hourly_earnings_yoy | NO |

ADP / claims / JOLTS were not used as substitutes.

FIELD SEMANTICS (PARSER / TESTS; NOT OBSERVED LIVE)
---------------------------------------------------
`Forecast` = SURVEY_CONSENSUS. Blank Forecast stays blank and is not
replaced by `TEForecast`.
`TEForecast` = PROVIDER_FORECAST.
`LastUpdate` = SOURCE_UPDATED_UTC.
`observed_at_utc` = local collector clock only.
No real prospective checkpoint was created. Window for
`usd_empsit_2026-10-02` still opens 2026-09-30T12:30:00Z.

ARCHIVAL PERMISSION
-------------------
NOT_CONFIRMED. HTTP 403 is not a license grant. Successful API access
would also not have been treated as archival permission.

ADAPTER / SCHEDULER
-------------------
Trading Economics adapter remains not live.
enabled=false. automation_class is not APPROVED_AUTOMATION_READY.
Official BLS adapter remains disabled.
Windows task unchanged. Expected scheduler TE requests: 0.

TEST RESULTS
------------
82 passed. Stage 6B 6, Stage 6A 5, Stage 4 10, Stage 5 7, Stage 1 12,
Stage 2 13, Stage 3 15, consensus Stage 2 14. No test network calls.

NEXT STEP
---------
Do not promote Trading Economics. Documented Calendar authentication
was used and still returned 403, so Calendar entitlement or another
unresolved access restriction remains. Investigate with the Trading
Economics dashboard or support without another automated recorder
request. Activation is a separate stage.
STOP.
