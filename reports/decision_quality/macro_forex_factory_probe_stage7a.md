# MACRO RESEARCH — FOREX FACTORY STAGE 7A
# OFFICIAL CALENDAR EXPORT CAPABILITY PROBE

Research/probe only. No autonomous source enablement. No HTML scrape.
`FORWARD_CONSENSUS_COLLECTION_ENABLED` remains false.
Windows task `ForexMacroProspectiveCollectDue` was not modified.

PHASE A — REPOSITORY AUDIT
--------------------------
Prospective recorder already has: event registry (`usd_empsit_2026-10-02`
T0=2026-10-02T12:30:00Z), source registry, operator ingest with
recorder-clock `observed_at_utc`, checkpoint scheduler, SHA-256 artifacts,
and distinct `source_updated_utc`. Trading Economics probes remain isolated
and TE is still disabled. No Forex Factory adapter, registry row, or
production import exists. Prior feasibility work excluded Forex Factory
scraping and listed "no official API"; that is distinct from the Weekly
Export download identified in Phase B.

PHASE B — OFFICIAL EXPORT
-------------------------
Identified from Forex Factory's own calendar UI "Weekly Export" (JSON/CSV/
XML/ICS) and Fair Economy, Inc. hosting:

`https://nfs.faireconomy.media/ff_calendar_thisweek.json`

Host: `nfs.faireconomy.media`. This is FEI's export download, not HTML,
not undocumented AJAX, not a third-party mirror.

PHASE C — PERMISSION
--------------------
Forex Factory Notices: FEED (calendar compilation) copying, republication,
and redistribution are explicitly prohibited without prior written consent.
Export existence is not a license. Automated retrieval is not explicitly
granted.

- automated retrieval: NOT_CONFIRMED
- local private retention: NOT_CONFIRMED
- redistribution: RESTRICTED

PHASE D — ONE REQUEST
---------------------
Count: 1. Guard rejects request #2. No HTML fallback. No retry.

HTTP **403 ACCESS_DENIED**. No calendar JSON rows. Field names and target
events were not observed from a live body.

FORECAST SEMANTICS
------------------
CONSENSUS_LIKE_NOT_CONFIRMED. A Forecast column is advertised on the public
calendar/export, but Forex Factory documentation reviewed here does not
establish a named economist survey. Not labeled SURVEY_CONSENSUS.

TIMEZONE
--------
UNSPECIFIED_OR_USER_LOCALIZED. Website times follow the user timezone
setting. The export is not documented as UTC. No silent conversion.

ARTIFACT
--------
`data/research/macro/consensus_pit/prospective/probes/forex_factory_stage7a.sanitized.json`
SHA-256: `17df9da368704b3ae88df2533d5d831a25bcd6b9d877aefe0ceb5653ec98e3ce`
Did not enter `observations/observations.jsonl`.

TEST RESULTS
------------
86 passed. Stage 7A 4, Stage 6B 6, Stage 6A 5, Stage 4 10, Stage 5 7,
Stage 1 12, Stage 2 13, Stage 3 15, consensus Stage 2 14. No test network
calls.

NEXT STEP
---------
Do not activate Forex Factory. Do not scrape HTML. Do not retry this
export from the recorder. A later explicit stage may review export access
or a licensed alternative after FEED-copying restrictions are resolved.
STOP.
