# Security review

## What this candidate cannot do

- It cannot open a network connection. The source does not import a client or a socket.
- It cannot read `.env`, the process environment, Windows Credential Manager, or production configuration.
- It has no functional live command. `--live` is a refusal. `run_live` raises before any prompt.
- It does not accept an arbitrary class, an `offline_fake` marker, or a copied marker on the normal path. Those objects are not constructed.
- It does not send POST, PUT, PATCH, or DELETE.
- It does not describe an account-summary, order, trade, position, transaction, or candle request.
- It does not retry, follow a redirect, or stream.
- It does not substitute a fixture price for a missing instrument. The normal fixtures are used only when the normal offline path is selected. A test record that omits a name fails closed.
- It does not invent a quote-age threshold.
- It does not calculate an executable size.

## Test injection

`run_test_case` is the only injector. It takes a list of `(status, body)` records. A class is rejected. The normal executable never calls this function. Passing a record does not prove that some other object is free of network access. The pytest fixture blocks DNS, socket creation, and connection attempts during the offline tests. That fixture is a testing safeguard, not a general security sandbox.

## Failure policy

The first failed request stops the session. Pricing does not run after an instruments failure. Non-200 bodies are not decoded. Exception text is `R55B2_REJECTED` or `R55B2_LIVE_DISABLED`. The synthetic account placeholder and the synthetic token must not appear in saved output or exception text. A designated output file is removed at the start of a run and replaced only after both responses validate.

Counters stay separate: requests attempted, HTTP 200 responses, and validated responses. A validated instruments response plus a rejected price is not a successful session. `rows` stays empty and no success file is kept.

## What remains unsafe to infer

A GET-only description does not make a future token read-only. Token permission stays `UNKNOWN`. Hidden input is not implemented here, and if it were, it would not protect a token from a debugger or process memory. This review does not authorise an authenticated request.
