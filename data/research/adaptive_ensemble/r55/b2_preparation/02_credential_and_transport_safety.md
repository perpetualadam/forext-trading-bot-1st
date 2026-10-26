# Proposed credential and transport safety

This is a procedure for a possible later session. It is not implemented here. No credential is requested now. No socket is opened now.

A GET-only client does not make the token read-only. The broker may still allow that token to place orders. Local status for token permission stays `UNKNOWN`.

## Approval before any connection

A future authenticated session would require a new written approval that names the exact executable hash to be run. The current B1 executable is not that program. Its `--live` path, `run_live()`, and `run_session(mode="live")` stay disabled. This preparation adds no CLI flag, environment switch, or connection entry.

The approval would have to be given by the user before the program asks for a credential. An environment variable, a module flag, or a token on the command line would not count as approval.

## Confirmation screen

After that separate approval, and before any credential callback, the program would show only:

- Host `api-fxtrade.oanda.com`
- Port 443
- Method GET
- Exact endpoints, in order: instruments, then pricing
- The six instrument names
- Maximum request count: 2
- Timeout: 5 seconds per request
- Certificate verification enabled
- Hostname verification enabled
- Redirects disabled
- Retries disabled
- No request body and no stream
- Trading actions prohibited
- Token permission `UNKNOWN`
- Account home currency `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`
- Spread-bet stake mapping `NOT_VERIFIED`
- Executable size `NOT_CALCULATED`

The screen would not show an account identifier, a token, an `Authorization` header, or a full account URL. The only continuation phrase would be the exact text `CONFIRM PREVIEW`. Any other answer, including a trailing space, would stop the session.

## Credentials

Only after that exact confirmation:

- Prompt `Account identifier: ` for the account identifier.
- Prompt `API token: ` through hidden input, not `input` and not a command-line argument.

Both values would stay in a memory object whose text form is `MemoryCredential()` and contains neither value. They would be used only to build the two in-memory requests. They would not be written to Git, JSON, logs, tracebacks, fixtures, screenshots, or chat.

The program would not read `.env`, Windows Credential Manager, production configuration, or the process environment for a token or account identifier.

Hidden input does not protect a token from a compromised terminal, a debugger, or process memory.

## Cancellation

Cancellation before confirmation: no credential prompt and no request.

Cancellation after confirmation and before the first request: discard the memory credential, retire any designated output path, and send nothing.

Cancellation after the first request has been sent: the first request cannot be unsent. The program would close the client, send no second request, discard the raw body, and write no success file. The counters would show one attempt and zero validated responses. A partial instruments payload would not be relabelled as a completed session.

## HTTP 401 and 403

A 401 or 403 would stop the session. The status would be recorded as a number only. The body would not be read, saved, or copied into an exception. The exception text would be a fixed code. The token and account identifier would not appear in that text. There would be no retry and no second endpoint after a refusal of the first.

The same body rule applies to 404, 429, and 5xx. A 429 would not be retried.

## Transport boundaries for a future design

These values match the current pinned gate. This document does not change them.

| Control | Proposed value |
| --- | --- |
| Host | `api-fxtrade.oanda.com` only. No host override. |
| Port | 443 |
| Method | GET only. POST, PUT, PATCH, and DELETE are rejected before a client exists. |
| Paths | `/v3/accounts/{accountID}/instruments` and `/v3/accounts/{accountID}/pricing` only. The account segment is the in-memory identifier. The saved evidence keeps the `{accountID}` pattern, not the identifier. |
| Query | Instruments: `instruments` only. Pricing: `instruments` and `includeHomeConversions=true` only. The instrument list is the six names in fixed order. |
| TLS | `CERT_REQUIRED` and hostname verification on. A context that fails either check is rejected. |
| Body | None. |
| Stream | False. |
| Redirects | False. Statuses 301, 302, 303, 307, and 308 are not followed and their bodies are not read. |
| Retries | 0. |
| Timeout | 5.0 seconds, passed as the per-request client timeout. |
| Response cap | 1,048,576 bytes. One extra byte is a `RESPONSE_TOO_LARGE` failure. The oversize body is not retained as evidence. |
| Order | Instruments, then pricing. Pricing starts only after the instruments response validates. |
| Orders and account changes | Paths containing orders, trades, positions, transactions, summary, or candles are outside the allowlist and are rejected before a client exists. |

## Failure behaviour

Malformed JSON, a non-object payload, an unexpected instrument name, a duplicate name, a non-finite number, a non-positive bid or ask, an ask below the bid, or a non-integer pip location fails closed. The classification is a fixed code such as `MALFORMED_JSON`, `SCHEMA_REJECTED`, `HTTP_ERROR`, `TIMEOUT`, `TLS_FAILURE`, `RESPONSE_TOO_LARGE`, or `UNEXPECTED`. The original exception text is dropped.

A missing allowlisted field is `NOT_RETURNED`. It is not replaced. A missing instrument is not filled from a fixture. `tradeable` other than true, or a missing timestamp, means that quote is not a usable price. No local rule defines how old a timestamp may be. That age limit is **DOCUMENTATION_VERIFICATION_REQUIRED**.

Counters stay separate:

- `requests_attempted` counts a request that was handed to the client.
- `successful_http_responses` counts HTTP 200 only.
- `validated_sanitised_responses` counts responses that passed the schema checks.

Two attempts are not success. A success file is written only when validated responses equal 2 and all six names are present in both responses. Any earlier failure retires the designated output path before the attempt, so a stale success file cannot remain.

## Timeout and session deadline

The five-second value is the existing per-request timeout. It is not a total session deadline. Two sequential requests can each wait up to five seconds. This plan does not claim that five seconds is long enough for the broker, and it does not change the value. Whether the broker's latency fits that cap is **DOCUMENTATION_VERIFICATION_REQUIRED**. A total session deadline would be a new control and would need its own approval and tests.

## What this document does not build

No live transport module, no activation command, and no change to B1. `run_test_session` remains a test-only interface. It is not a network sandbox and it is not a future live entry.
