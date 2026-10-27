# V2.6 Test Results

All tests are synthetic HTTP or filesystem fixtures. Command:
python -I -S -B data/research/trading_intelligence_v2/v26_run.py --tests
Offline demonstration/report command: same runner --offline-check.
Both install the audit barrier before importing project modules. Socket events,
operational imports, credentials, journals, subprocesses and writes outside this
stage's research outputs/reports are blocked. No authenticated OANDA request occurs.

Targeted tests exercise allowlists before send, redirects, token redaction, scoped
approval refusal, mocked HTTPS backend, rate/retry/timeout budgets, cancellation,
JSON/price/time validation, partial publication, original retrieval-time resume,
hash tampering, writer exclusion, six-pair aggregation and independence gates.
Executed results and earlier-version regressions are recorded in test_results.json;
cross-platform findings and raw source preservation are in verification.json.
Hosted outcomes are recorded separately after publication. Historical full-suite
failures remain visible; overall CI must not be described as green if they persist.

Production remains NO-GO.
