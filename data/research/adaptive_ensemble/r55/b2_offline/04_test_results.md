# Offline test results

Command:

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r55/b2_offline/test_b2_offline.py -q`

The autouse fixture was active for every test. It replaces DNS lookup, `socket.create_connection`, and `socket.socket`. One test calls all three and requires `AssertionError: network`. The fixture is a testing safeguard, not a sandbox.

Attempt 1: 26 passed, 2 failed, 0.38 seconds.

`test_invalid_prices_are_rejected` and the untradeable case inside `test_output_stays_synthetic` expected `validated_sanitised_responses == 0`. The instruments response had already validated, so the count was 1. The price failure was recorded, `rows` was empty, and no success file remained. The assertions were changed to require that failure record, an empty row list, and a validated count of 1. The rejection itself was not removed.

Attempt 2: 28 passed, 0 failed, 0.31 seconds.

No production test suite, database script, Docker, or WSL command was run. No OANDA connection was opened.

The 28 tests cover disabled launch, live refusal, built-in fixtures, rejection of injected classes, the two GET descriptions and their order, no third request, rejection of summary and order endpoints, rejection of other methods and overrides, first-request failure, HTTP 401, 403, 404, 429, 500, and 503, malformed JSON, oversized bodies, invalid prices, bid above ask, missing names, unresolved conversions, timestamp classification, no staleness threshold, secret redaction, stale-file removal, synthetic labels, the network fixture, and unchanged B1 and dependency hashes.
