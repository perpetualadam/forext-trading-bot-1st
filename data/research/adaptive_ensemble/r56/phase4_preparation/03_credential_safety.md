# R.56 Phase 4 credential safety

Real credentials are not authorised. This phase does not read `.env`, a credential store, or a command-line token. It does not persist a token. It does not log an Authorization header or a raw response body.

## Implemented boundary

`SyntheticCredential` is the only accepted provider.

- Classification: `SYNTHETIC_TEST_ONLY`.
- Token prefix: `SYNTHETIC-TOKEN-R56P4-`. The full synthetic token is `SYNTHETIC-TOKEN-R56P4-NOT-REAL`.
- Account identifier: the Phase 3 synthetic value `001-001-0000000-001`.
- `authorization_present()` returns a boolean. It does not return the token.
- Any other class, classification, prefix, or account identifier raises `REAL_CREDENTIAL_PROVIDER_REJECTED` before a request is built.
- `read_real_credential()` raises `REAL_CREDENTIAL_INPUT_NOT_AUTHORISED`.
- `HIDDEN_INPUT = NOT_IMPLEMENTED`. There is no hidden prompt.

A serialised session that contains the synthetic token, the synthetic account identifier, or the text `Bearer ` is replaced with `SENSITIVE_OUTPUT_BLOCKED` and the leaked record is not written. Exception text is not copied into the log. The stored code is `EXCEPTION_CONTAINED`.

## Future confirmation, not implemented

A later authorised session would need a separate written authorisation. Before any credential is read, an operator would confirm, in that future program, that the only HTTP operations are:

1. `GET /v3/accounts/{accountID}/summary`
2. `GET /v3/accounts/{accountID}/pricing` with the six configured instruments and no other query key.

That confirmation step is documented here and is not built. A real API token may still have trading authority even if those two calls are GET requests. This candidate cannot send orders, and it also cannot be used as a live client.
