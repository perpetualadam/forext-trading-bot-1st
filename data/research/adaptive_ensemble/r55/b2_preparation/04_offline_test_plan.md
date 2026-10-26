# Offline test plan

This is a plan for tests that would be written later, against a future offline harness. Those tests do not exist for Boundary B2. None of them has been run. None is marked passed.

The future harness would use injected responses and a network-denial fixture. The fixture would block socket creation, DNS resolution, and connection attempts. It would be a testing safeguard, not a sandbox. The tests would not call OANDA, would not read a real credential, and would not import `forex_bot.config` or `forex_bot.oanda_client`.

A test would count as passed only after a recorded command, an observed pass count, and the expected result below. This document is not that record.

| # | Test | Expected result | Evidence required before it can be called passed |
| --- | --- | --- | --- |
| 1 | Default launch | No arguments, and any unrecognised argument, print the disabled sentence and return without a credential prompt or a client. | Future log showing the disabled sentence and zero client constructions. |
| 2 | Live mode before a separate approval | `--live`, `run_live()`, and `run_session(mode="live")` stop before callbacks and before a client. B1 already does this. A new executable would have to show the same closed behaviour until its own approval names it. | Source citation plus a future test that a callback counter stays at zero. |
| 3 | Preview before credentials | The confirmation reader runs before the account reader and the token reader. The preview contains the host, GET, both endpoint names, the six pairs, maximum 2, and 5 seconds per request. It contains no token, account identifier, or full URL. | Future assertion log of reader order and preview text. |
| 4 | Confirmation refusal | Any answer other than exact `CONFIRM PREVIEW` requests no credential and builds no client. The designated output path is removed if it existed. | Future log with reader order `confirm` only, and the stale file absent. |
| 5 | Allowlists | Host, method, path, and query must match the two GET patterns. Another host, path, instrument, or query key is rejected before a client exists. | Future rejection log for each illegal value, with a fixed error code. |
| 6 | POST, PUT, PATCH, DELETE | Each method is rejected before a client exists. | Four future rejection records. |
| 7 | Orders and trades | Paths for orders, trades, positions, transactions, and account changes are rejected before a client exists. | Future rejection records. No request body is sent. |
| 8 | Redirects, retries, and streaming | Redirect statuses are not followed and their bodies are not read. `retries` is 0. `stream` true is rejected. A failure does not cause a second call. | Future counts: one attempt, zero body reads on the redirect, no second endpoint. |
| 9 | TLS and hostname | The context must be `CERT_REQUIRED` with hostname checks on. A weaker context is rejected. | Future assertion of those two settings. |
| 10 | Timeout and oversize | A timeout classifies as `TIMEOUT`, closes the client, and does not retry. A body over 1,048,576 bytes classifies as `RESPONSE_TOO_LARGE` and is not saved. | Future counter line: attempted 1, validated 0, no success file. |
| 11 | HTTP 401, 403, 404, 429, and 5xx | Each status fails closed. The body is not read. The token is not copied into the error. 429 is not retried. | Five future cases, each with a numeric status and a fixed classification, and a scan showing the synthetic secret is absent. |
| 12 | Malformed JSON and unexpected shapes | Invalid JSON, a non-object, and a missing `instruments` or `prices` list fail as `MALFORMED_JSON` or `SCHEMA_REJECTED`. | Future classifications and a validation count of 0. |
| 13 | Missing instruments or prices | An unexpected name is rejected. A missing one of the six does not receive a fixture price. The session does not write a success file that claims all six were returned. | Future file-absent check and `NOT_RETURNED` or a schema failure, with no substituted price. |
| 14 | Stale or untradeable quotes | `tradeable` false, or a missing timestamp, does not become a usable price. No second price is invented. An age cutoff is not asserted, because none is documented locally. | Future row or rejection showing the quote was not accepted as usable. |
| 15 | Invalid numbers | NaN, infinity, a non-numeric price, a non-positive price, an ask below the bid, and a non-integer pip location fail closed. | Future schema rejections. No spread is emitted for those rows. |
| 16 | Missing or ambiguous GBP factors | Absent factors stay `NOT_RETURNED`. Positive and negative factors are not copied onto each other. Gain and loss are not copied onto each other. `1.35` is rejected if it appears. | Future row snapshot and a scan for `1.35`. |
| 17 | Home-currency evidence | A quoted conversion currency, including a planted `GBP`, leaves `account_home_currency` at `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` and `quoted_conversion_currency_is_account_home` at `NO`. Conflicting labels do not verify the account. | Future assertions of those two constants. |
| 18 | Synthetic versus live labels | Fixture output is only `SYNTHETIC_TEST_ONLY`. A document labelled `ACCOUNT_VERIFIED` is rejected. A future real parse, if separately authorised, would be `READ_ONLY_RESPONSE_NOT_ACCOUNT_VERIFIED` and still would not verify the account. | Future label checks. This plan has not produced a live document. |
| 19 | Secret redaction | The synthetic test secrets, `Bearer`, `Authorization`, `https://`, and the account identifier are absent from JSON, stdout, and exception text. | Future scan of output and exception strings. |
| 20 | Partial failure | A failure on the first request does not send pricing. A failure on the second does not leave a previous success file. Validation count stays below 2. | Future pre-written file removed, second call count zero when the first fails. |
| 21 | Network blocking | The offline suite runs with DNS, socket creation, and connect attempts blocked. A stand-in that calls those functions is intercepted. The fixture is not described as a sandbox. | Future test output showing the denial fired and no external connection was opened. |
| 22 | Preservation | Production modules are not imported. The eight pinned research hashes still match. B1 `session_main.py`, `transport.py`, and `test_session.py` still match the hashes in `06_baseline_and_integrity.md`. | Future hash printout. Not a licence to edit those files. |

The B1 offline suite already covers the disabled live entry and the synthetic session. Those B1 results are not reclassified as B2 tests, and they are not repeated by this preparation.
