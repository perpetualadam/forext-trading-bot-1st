# R.56 Phase 5 credential security

Real credential use is not authorised. Phase 5 has no working path to a token.

## What the code will not do

- It does not read `.env`, the environment, or a credential store.
- It does not put a token in source, on a command line, or in a child job.
- It does not write a token, an Authorization header, or an account identifier to a log.
- `prompt_hidden_token`, `read_environment`, `read_dotenv`, and `activate_live` raise `REAL_CREDENTIAL_USE_NOT_AUTHORISED`.
- `confirm_live` raises `LIVE_CONFIRMATION_NOT_AUTHORISED`.
- There is no environment switch that enables a real token.

## Synthetic marker

`SyntheticCredential` holds the marker `SYNTHETIC-NOT-REAL` in memory. `accept_offline` returns true or false and does not return the marker. Any other class, marker, or account id is rejected. The child job carries `authorization_present: true` and `credential_classification: SYNTHETIC_TEST_ONLY`. A job that contains a token or account-id field is `JOB_SECRET_REJECTED` and the value is not echoed.

Stdout that contains an account-id pattern, the synthetic marker, or `Bearer ` is replaced with `SENSITIVE_OUTPUT_BLOCKED`. Stderr is discarded. Exception text is not copied into the result; the code is `EXCEPTION_CONTAINED`.

## Confirmation before credentials

The supervisor renders the screen and requires the phrase `SYNTHETIC OFFLINE CONFIRM` before `accept_offline` is called. The screen states OANDA LIVE, the host, the two GETs, the six pairs, that no order or position change is included, that a token may still have trading permission, that the production bot must stay stopped, the log directory, and the 5 second, 15 second, and 1 MiB limits. It also states that the confirmation does not authorise a network connection.

A future hidden prompt is described in `06_future_live_session_procedure.md`. It is not implemented.
