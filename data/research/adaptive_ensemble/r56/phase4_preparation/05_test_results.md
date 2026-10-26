# R.56 Phase 4 test results

Command:

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase4_preparation/test_phase4_offline.py -q`

Result: **24 passed, 0 failed, 0 skipped, 0.53 s**.

Network blocking stayed active for the run. `socket.socket` and `socket.getaddrinfo` raise `network_blocked`. No production module was imported. No order request was built.

## Coverage

The 24 tests group the required checks:

- Activation: default arguments, `--live`, `--connect`, `--authenticate`, and a token argument return exit code 2 and write nothing. `--offline` returns 0 and writes one synthetic session.
- Real credential provider and `read_real_credential()` are rejected. `HIDDEN_INPUT` is `NOT_IMPLEMENTED`.
- Source scan: no production or trading-engine imports, no socket import, no `os.environ`, `getenv`, or proxy variables.
- Fixed host, port, HTTPS, and GET. Summary and pricing patterns accepted. Unknown, orders, trades, and positions paths rejected by the Phase 3 gate.
- Duplicate summary, pricing before summary, and a third request rejected by the transport.
- Unknown query key, a short instrument list, a body, a redirect, a retry, and streaming rejected.
- Valid synthetic summary and six-instrument pricing. Missing currency, missing bid, and a non-positive price stay diagnostic and unresolved.
- Malformed JSON, HTTP 401, 403, 429, and 500. A 502 on the pricing leg keeps the account diagnostic and does not mark the session complete. Error bodies are not logged.
- Body above 1 MiB is `RESPONSE_TOO_LARGE`.
- Stalled connect, TLS, headers, and body read. Slow body. Per-request and session budgets. A sleep that ignores its budget.
- Token, account identifier, and exception text absent from logs. Unknown fields dropped. Logs only under `phase4_preparation/synthetic_logs`. Outside that directory raises `LOG_PATH_OUTSIDE`.
- `executable_order` is `NOT_PRODUCED`. No sizing decision and no `1.35` fallback.
- Phase 2 and Phase 3 file hashes, and `forex_bot/oanda_client.py`, asserted inside the suite.

## Exclusions

Live DNS, live TLS, live sockets, a 15-second wall wait, and process isolation were not exercised. `live_socket_timeout` remains `NOT_EXERCISED`.
