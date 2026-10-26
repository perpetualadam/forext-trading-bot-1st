# Request and credential security

The transport exposes two methods. There is no generic request function and no caller-supplied URL.

1. `GET https://api-fxtrade.oanda.com:443/v3/accounts/{accountID}/summary`
2. `GET https://api-fxtrade.oanda.com:443/v3/accounts/{accountID}/pricing?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF`

Offline mode accepts only the selector `SYNTHETIC_PIN` and substitutes the Phase 5 pinned id. Any other selector is `REAL_ACCOUNT_ID_REJECTED`.

Authenticated mode accepts an account id only when it matches `^[0-9]{3}-[0-9]{3}-[0-9]{1,20}-[0-9]{3}$`. That is four digit groups: site (3), division (3), user (1 to 20), and account (3). Control characters, whitespace, slashes, backslashes, and the URL delimiters `? # @ : ; & % =` are rejected. The synthetic selector and the synthetic pin are `SYNTHETIC_ACCOUNT_REJECTED` in this mode, so the authenticated request does not use them. `build_prepared` substitutes the validated id into the two fixed tails. A malformed id raises before `HarnessConnection.perform` and before `HTTPSConnection`.

POST, PUT, PATCH, DELETE, other hosts, HTTP, orders, trades, positions, bodies, redirects, retries, cookies, streams, and extra query keys are rejected by `validate_outbound`. TLS must stay `CERT_REQUIRED` with hostname checks. `disable_tls_verification` always raises. Non-200 bodies, including 401, 403, 429, and 5xx, are not logged. A body over 1,048,576 bytes is `RESPONSE_TOO_LARGE`. Redirect status codes 301, 302, 303, 307, and 308 are `REDIRECT_REJECTED`. The real branch does not retry. Harness mode accepts only a synthetic bearer token. Real-mode header syntax accepts a 16 to 128 character token without that marker, then still requires the source switch, a parent capability, and the two-GET checks before any socket. A well-formed token is not a grant.

## Credential frames

Offline schema `r56.phase6.ipc.1` still carries `classification`, `account_selector`, and `marker` on one stdin frame. Mode must be `OFFLINE_TEST`.

Authenticated schema `r56.phase6.ipc.2` is a separate frame. Its public keys are `schema`, `mode`, `step`, `prior`, `session_id`, `collected_at`, and `fixture`. The credential object has exactly `account_id` and `token`. Mode must be `AUTHENTICATED_HARNESS`. `REAL_SESSION` is `REAL_OANDA_SESSION_NOT_AUTHORISED`. The token must start with `SYNTHETIC-`, contain `NOT-REAL`, and contain no whitespace or URL delimiter. Nested values, a second JSON value, and a frame over 262,144 bytes are rejected. The returned job does not keep the credential. Exception text is the code only.

The harness authorisation object carries `capability` instead of a confirmation phrase. The capability is 64 hex characters, a dot, and a 64-character HMAC. The HMAC key stays in the parent `CapabilityIssuer`. The parent redeems it once, using the capability mode on the same dispatch contract that issued it, then answers `CAP_OK` or `CAP_NO` on the same stdin pipe. A harness mode cannot redeem a real binding, and a real mode cannot redeem a harness capability. `CAP_NO`, a missing capability, a wrong session, a wrong step, a replay, and an expired value never reach `HarnessConnection.perform`. The value is not a secret in the cryptographic sense of server authentication, and it is not written to argv, the environment, or the session log. A harness capability cannot satisfy `assert_parent_capability`.

The offline child and the `--authenticated-worker --harness-transport` child each read one stdin frame. Bare `--authenticated-worker` checks the source switch and returns before it reads stdin. The worker does not call `confirm_one_session` or `issue_runtime_authorisation`. `prompt_hidden_token` and `prompt_account_id` check the source switch and the runtime grant before `getpass` or terminal input. While the switch is false those prompts are not called. `read_environment` and `read_dotenv` raise before any file read. `consume_real` checks the source switch before it parses a frame. Nothing in this phase reads `.env`.

## Redaction

Before stdout or a session log is written, the exact supplied account id, the exact token, the bearer header, and an `Authorization:` header are treated as secrets. A match replaces the payload with the allowlisted `SENSITIVE_OUTPUT_BLOCKED` record. This does not depend on the account id matching `\d{3}-\d{3}-\d{3,}-\d{3}`. Child stderr is discarded and is not printed. The parent does not persist raw child stdout when that scan matches.

Python is not claimed to erase the string from memory.

## Session authorisation record

`network_permitted` is the verified session authorisation state. It is true only when the parent holds `_VerifiedRealAuthorisation` on a `REAL` dispatch and `REAL_SESSION_SOURCE_ENABLEMENT` is true. A child payload, a forged result label, and `dispatch_mode="REAL"` by itself do not set it. `network_attempted` and `broker_response_received` are separate. A response is not recorded unless an attempt happened. `REAL_NETWORK_COMPLETED` and `SESSION_COMPLETE_REAL_DIAGNOSTIC` require authorisation, a received response, error `NONE`, and a reaped child. Synthetic records stay `network_permitted` false with synthetic labels. Real records stay out of `synthetic_logs`.
