# Future offline security tests

These tests are not implemented in B3 and have not been run. None is marked passed. They would use fake responses and a network-denial fixture. They would not call OANDA, read a real credential, or import production modules. The fixture would block DNS, socket creation, and connects. It would be a test safeguard, not a sandbox.

A test is passed only after a recorded command, a pass count, and the result below. The independent B2 review, 27 passed and 1 deselected, is not this list and does not approve a connection.

| # | Test | How to run it offline | Pass criterion |
| --- | --- | --- | --- |
| 1 | No credential access before confirmation | Fake readers that raise if called. Run through preview only. | Account and token readers are not called. No client object. |
| 2 | Confirmation refusal | Answer other than exact `CONFIRM PREVIEW`. | Stop. Readers not called. No client. |
| 3 | Cancellation before connection | Confirm, then cancel before the client constructor. | Constructor count is 0. Memory credential discarded. |
| 4 | Maximum two GET attempts | Supply three fake responses. | Third response is never read. Attempt count is 2 only when both succeed. |
| 5 | Exact host and port | Mutate host and port on a description. | Rejected before the fake client is constructed. |
| 6 | Exact endpoint allowlist | Descriptions for the two Option A paths, then a wrong path. | The two pass the planner. The other raises. |
| 7 | Account summary | Kind `summary`. | Rejected before a client. |
| 8 | Orders and trades | Kinds `orders`, `trades`, `positions`. | Rejected before a client. |
| 9 | Non-GET methods | POST, PUT, PATCH, DELETE. | Each rejected before a client. |
| 10 | TLS verification | Fake context with certificate checks off, then hostname checks off. | Both rejected before a request. The accepted context is `CERT_REQUIRED` with hostname checks on. |
| 11 | Redirect rejection | Fake status 302. | Not followed. Body not read. No second host. |
| 12 | Retry rejection | Fake 429 and a transport with retries set to 1. | One attempt. The retries value is rejected. |
| 13 | Streaming rejection | `stream` true. | Rejected before a client. |
| 14 | Response-size enforcement | Buffer of 1,048,577 bytes. | `RESPONSE_TOO_LARGE`. Bytes absent from the output. |
| 15 | Per-request timeout | Fake client that raises `TimeoutError` on the first call. | Classification `TIMEOUT`. Socket closed. No second call. |
| 16 | Total-session deadline | Fake clock advancing past 15 seconds before request 2, or a first call that blocks. | Request 2 is not started. This is the test that would show the deadline is enforced. Until it passes, the 15-second value is only configured. |
| 17 | HTTP errors | Fake 401, 403, 404, 429, 500, and 503. | Fail closed. Body not decoded. Status number only. |
| 18 | Malformed JSON | Status 200 and body `{`. | `MALFORMED_JSON`. No success file. |
| 19 | Invalid numeric fields | Negative, zero, NaN, infinity, and bid above ask. | `SCHEMA_REJECTED`. No price row kept. |
| 20 | Missing conversion factors | Omit the conversion objects. | Factors `NOT_RETURNED`. Home currency stays unverified. No `1.35`. |
| 21 | Missing or invalid timestamps | Omit `time`, then set `time` to `yesterday`. | `MISSING_TIMESTAMP` and `MALFORMED_TIMESTAMP`. A syntactically valid old timestamp does not become fresh. |
| 22 | First-request failure | Instruments status 500. Pricing fake ready. | Pricing reader is not called. Rows empty. |
| 23 | Second-request failure | Instruments valid, pricing 500 or bad JSON. | Attempt count 2. Validated count 1. No success file. |
| 24 | Secret redaction | Synthetic token and account identifier in a fake body and a reader error. | Absent from stdout, exceptions, and the file. |
| 25 | No stale success artifact | Pre-write a success file, then fail request 1. | That file is gone. |
| 26 | No production imports | Load the future modules under a fake import hook, or scan `sys.modules` and the source. | `forex_bot.config` and `forex_bot.oanda_client` are absent. |
| 27 | Network denial | Autouse patch on DNS, `socket.socket`, and `create_connection` for the whole file. | Each probe raises. No test is described as a sandbox. |
| 28 | Preservation | Hash B1, the five B2 Python files, and the eight pins from disk. | Digests equal the values in `07_baseline_integrity.md`. |

Tests 15 and 16 are the ones that would move timeouts from configured constants to enforced behaviour. They do not exist yet.
