# V2.7 decision — offline implementation only

`TIV27_DIRECT_OANDA_WORKFLOW_VERIFIED_OFFLINE`

This verifies the standalone frontend and its synthetic integration, not current
OANDA connectivity or an executable real-session grant. The command still refuses
before confirmation, token entry, worker startup and network access. No actual
token, .env, production credential value or R.56 permit contents were read. No
OANDA API host was contacted.

R.56 performed an account summary and six-pair current-pricing diagnostic. Its
credential_ipc.prompt_account_id/prompt_hidden_token and diagnostic_supervisor/
RestrictedLiveTransport/LiveExchange implement the original terminal and request
path. The prompt functions cannot be detached from their R.56 grants safely;
their Windows hidden-input mechanism is reused in a bounded standalone provider.
R.56 was not invoked or modified; its source gate remains False and permit/marker
metadata is unchanged.

fetch_ohlcv_range is the operational historical function and needs no run_bot call,
but its Config/dotenv import, midpoint batching and retries are unsuitable for this
bounded MBA request. Reuse its reviewed request contract via existing SPEC and
the research read-only adapter. No broad V2.6 rebuild was necessary for this task;
the existing controller, restricted HTTPS, validator and protected archive suffice.

New command: python -I -S -B data\research\trading_intelligence_v2\historical_session_entry.py

It currently exits 2 with AUTHENTICATED_EXECUTION_DISABLED. The future admitted
path uses a distinct historical confirmation and hidden token only, no account ID.
No new downloader, transport, journal, archive or grant issuer was built. The
unchanged gate precedes a narrowly scoped terminal-provider hook; its input is
bounded by the same session deadline and delivered only after durable reservation.

Research compatibility is normalized Bar/V2.3 schema compatibility, not acceptance
as an independent licensed six-pair dataset. The original importer still rejects
broker URLs; no rights or independence checks were weakened. Frozen policies and
original profit protection are unchanged. Synthetic fixtures were not evaluated
as market history, and the previously examined interval is connectivity-only.

Files: direct_history.py, historical_session_entry.py, test_v27.py; a narrow
provider hook in oneshot.py, explicit test modes in v26d_run.py, one focused CI job,
and these five requested reports. No operational files or existing safety assertions
changed. Existing scheduler work/local data were preserved and excluded from Git.

Focused tests and native publication passed; see V27_TEST_RESULTS.md. Publication
records exact commit and hosted CI in the delivery message after push. No activated
real-credential or live-request mechanism is published; real admission stays absent.

Before the first response, review/approve the exact proposal and remaining admission,
endpoint/account/retention conditions in V27_FIRST_REQUEST_APPROVAL.md. Approval of
one request never authorises a multi-year archive. No real data was acquired here.

**STOP AFTER V2.7 IMPLEMENTATION/PREPARATION. PRODUCTION TRADING REMAINS NO-GO.**
