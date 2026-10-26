# Architecture and request flow

This is a design for a possible later session. It does not add an HTTP client, a credential reader, or a live command. Passing this design authorises no connection.

The request shape stays Option A. The planner already in `r55/b2_offline/request_plan.py` allows only:

1. `GET /v3/accounts/{accountID}/instruments`
2. `GET /v3/accounts/{accountID}/pricing` with `includeHomeConversions=true`

Host `api-fxtrade.oanda.com`, port 443, maximum two descriptions, no body, no stream, no retry, no redirect. Account summary, orders, trades, positions, transactions, and candles stay banned. This design does not widen that allowlist.

## Components

| Component | Role in a future session | Present now |
| --- | --- | --- |
| A. Request planner | Reuse the B2 planner unchanged. It checks the account identifier only to reject empty or unsafe characters, then emits path patterns with `{accountID}` and does not copy the identifier into the description. | Implemented offline. It does not open a socket. |
| B. Credential boundary | After exact confirmation, ask for the account identifier and a hidden token. Hold both in a memory object whose text form contains neither value. Drop them on cancellation, failure, and completion. Never write them. | Not implemented. B2 `FUTURE_LIMITS` marks credential entry `NOT_IMPLEMENTED`. |
| C. HTTPS transport | One fixed-host GET client, created only after confirmation and only for the two planned descriptions. TLS certificate and hostname checks required. Close the socket in `finally`. | Not implemented. B2 has no `http.client` and no socket import. |
| D. Response validator | Reuse the B2 structural checks on bytes that came from the transport. Fixture bytes must not be substituted when a real read fails. A real parse would be labelled `READ_ONLY_RESPONSE_NOT_ACCOUNT_VERIFIED`, not `SYNTHETIC_TEST_ONLY`, and still would not verify the account. | Implemented for supplied bytes only. Current successful output is `SYNTHETIC_TEST_ONLY`. |
| E. Evidence writer | Write one sanitised file only after both responses validate. Omit the token, account identifier, `Authorization` header, full URL, raw body, balance, NAV, positions, and orders. Remove any previous file at start so a failure cannot leave a success artifact. | Offline writer exists for synthetic documents. It is not a broker-evidence writer. |
| F. Session controller | Run the sequence below. Stop on the first failure. Do not start request 2 if request 1 fails. | B2 `launch` runs fixtures only for exact `--offline`. Exact `--live` prints a refusal and does not call `run_live`. `run_live` raises `R55B2_LIVE_DISABLED` and stops. |

`run_test_case` remains a test injector for synthetic records. It is not a future live entry and not a sandbox.

## Ordered flow

```text
launch
  |-- any argument other than the future approved command
  |     -> disabled sentence, no prompt, no socket
  |
  +-- future command, only after Gate 2 exists and Gate 3 names its hash
        1. Show the preview. Do not open a socket.
        2. Wait for exact CONFIRM PREVIEW.
           Any other answer -> stop, no credential, no socket.
        3. Hidden local prompts for account identifier, then token.
           Cancel here -> discard memory, no socket.
        4. Planner builds the two descriptions. Reject anything else.
        5. Monotonic session clock starts. Deadline 15 seconds for the whole session.
        6. Request 1: DNS, TCP, TLS, GET instruments, read at most 1 MiB.
           Per-request cap 5 seconds. Failure -> close, no request 2, no success file.
        7. Validate instruments. Failure -> no request 2, no success file.
        8. Request 2: GET pricing, same caps.
           Failure -> close, no success file.
        9. Validate pricing. Both must pass before a file is written.
       10. Discard credentials. Print counts and the evidence label only.
```

An already-sent request cannot be withdrawn. Cancellation after request 1 has left the machine still forbids request 2 and forbids a success file.

## What this document does not build

No new Python module, no CLI flag, and no call to OANDA. Gate 2 would be required before any of the unimplemented boxes become code. Gate 3 would be required before that code is allowed to prompt or connect.
