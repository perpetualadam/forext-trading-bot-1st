# R.56 Phase 5 test results

Command:

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase5_connection/test_phase5_offline.py -q`

Result: **13 passed, 0 failed, 0 skipped, 3.94 s**.

The test process blocks `socket.socket`, `create_connection`, and `getaddrinfo` before the modules load. Each child process seals network entry points again. No production module was imported. No order request was built.

## Coverage inside the 13 tests

- GET-only, exact paths, fixed host and port, HTTPS, synthetic account-id substitution, the six-pair query.
- No redirect, retry, proxy inheritance, body, arbitrary URL, or third child.
- Orders, trades, position close, candles, and instrument paths rejected.
- TLS verification cannot be turned off. The live connection function raises before `HTTPSConnection`.
- Real credential activation, live confirmation, and `--live`, `--connect`, `--authenticate` fail closed.
- Synthetic credential accepted in memory. Marker and account id absent from logs and from the child argv.
- Sensitive stdout and a sensitive exception do not reach the log.
- Summary before pricing. Summary HTTP 500 does not start pricing. Pricing HTTP 502 does not complete the session.
- Malformed JSON, a body over 1 MiB, HTTP 401, 403, 429, and 5xx.
- Child hang, ignored sleep, crash, malformed stdout, and leaked fields. The parent reaps the child and does not record success.
- Confirmation is required before credentials. Logs stay under `phase5_connection/synthetic_logs`.
- Phase 2, 3, and 4 manifests, `oanda_client.py`, `oanda_account_adapter.py`, and `main.py` hashes match the recorded pins.

## Exclusions

No packet was sent to OANDA. The TLS assertion inspects a local `SSLContext` only. The 5 second and 15 second caps were enforced as maximums; the termination measurement used a 0.5 second deadline and is recorded in `04_process_timeout_evidence.md`.
