# V2.6B Credential Handling

Inspected oanda_history_transport.py without accessing any secret. It accepts
an in-memory token only for the real HTTPS backend after scoped approval checks.
There is no credential loader, token CLI option, subprocess handoff or .env read.
The token is placed only in the Authorization header. Repr and errors are redacted;
headers/error bodies are not persisted. Strict candle validation precedes archive
publication, rejecting unexpected credential-like response fields.

Synthetic tests confirm token-free URLs/fixture mode, redacted failures and no
secret persistence. The original V26 mocked-HTTPS test covers the header path.
No Windows Credential Manager or actual token was accessed.

https://developer.oanda.com/rest-live-v20/authentication/
Public authentication documentation describes a personal token with broader
account/subaccount capability. Transport restrictions are application controls,
not broker-side read-only token permissions.

No insecure loader defect was reproduced. Future proposal: reviewed user-controlled
in-process hidden input, fail closed without a genuine no-echo terminal, no shell
or subprocess arguments, no logging of object dictionaries. Python string memory,
swap and privileged inspection are not guaranteed secret erasure. The actual
credential source remains unverified and requires separate authorisation.

No authenticated requests. Production remains NO-GO.
