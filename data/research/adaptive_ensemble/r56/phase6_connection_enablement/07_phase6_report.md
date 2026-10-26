# R56_PHASE6_AUTHENTICATED_PATH_CORRECTION_REPORT

Overall: **PASS**

`TARGET_ENVIRONMENT = OANDA_LIVE`

`LIVE_NETWORK_ACCESS = NOT_AUTHORISED`

`REAL_SESSION_SOURCE_ENABLEMENT = False`

No OANDA connection was made. The production bot was not started. Real credentials were not read. The source switch was not set true.

## Correction

Offline mode still seals the network and still uses `FakeExchange` with `SYNTHETIC_PIN`. The authenticated path now selects `LiveExchange` only when a test injects `HarnessConnection`. That object returns scripted bytes and is not a socket. The real `HTTPSConnection` branch still raises `REAL_OANDA_SESSION_NOT_AUTHORISED` before it runs, and it now also requires a runtime grant that is not issued.

Authenticated account ids are checked against `^[0-9]{3}-[0-9]{3}-[0-9]{1,20}-[0-9]{3}$` and substituted into the two fixed paths. The synthetic pin is rejected on that path. Schema `r56.phase6.ipc.2` carries the token and account id on one frame. The later activation-preparation report covers the child process that reads that frame under `--harness-transport`. Bare `--authenticated-worker` still does not read it.

Exact account-id and token values are removed before stdout or a log write, including an id that does not match the older `\d{3}-\d{3}-\d{3,}-\d{3}` scan. Child stderr is discarded.

## Tests

The Phase 6 file is the only suite that was run. The passing run after the correction is recorded with the final count in the chat report. No external host was contacted.

## Before a real session

A new written authorisation must name the two live GETs, the source constant must be changed on purpose, and a runtime grant must be issued. This report does not do any of those. The production bot stays stopped.

Production deployment remains **NO-GO**.
