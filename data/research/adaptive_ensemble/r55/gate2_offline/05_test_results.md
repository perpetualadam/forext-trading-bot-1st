# Test results

Command:

`python -B -m pytest -p no:cacheprovider --noconftest -s --tb=line data/research/adaptive_ensemble/r55/gate2_offline/test_gate2_offline.py`

The network-denial fixture was active for every test. It replaces `socket.getaddrinfo`, `socket.create_connection`, and `socket.socket`. A direct call to each one raised `AssertionError`. The fixture is not a sandbox.

No test was deselected. B1, B2, the eight dependency pins, the six operational files, and the eight B3 design documents were hashed from disk during the run.

## Attempt 1

69 passed, 10 failed, 7.97 seconds.

The failures were in the test helper. `HERE.parents[5]` pointed at the Desktop directory instead of the repository, and the redaction dump tried to serialise a `Path`. The security assertions were not removed or loosened. The product code was not changed to make those 10 cases pass.

## Attempt 2

79 passed, 0 failed, 0 skipped, 7.72 seconds.

Coverage includes the disabled CLI, rejection of `--live`, `--connect`, `--authenticate`, `--offline`, and `--trade`, sealed live factory, confirmation refusal, cancellation, synthetic credentials, redaction, fixed host and port, GET-only, the endpoint allowlist, account summary, orders and trades, raw URLs, body, stream, redirect, retry, the two-request maximum, instruments before pricing, first-request failure, HTTP 401, 403, 404, 429, 500, and 503, malformed JSON, the 1 MiB cap, invalid prices, missing conversions, missing and malformed timestamps, a 1999 timestamp left `NOT_VERIFIED`, per-request and session deadlines, stalled resolve, connect, handshake, and headers, a slow body, a non-cooperative blocker, stale success removal, production-import scan, and unchanged prior hashes.

`run_live` was not called on B1 or B2. This suite did not import `forex_bot.config` or `forex_bot.oanda_client`.
