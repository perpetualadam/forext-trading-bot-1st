# Preview, confirmation, and credential entry

`run_session` is the executable orchestration. `run_test_session` is test-only and is not called by `launch` or `run_offline`.

1. Build the non-sensitive preview.
2. Ask the confirmation reader.
3. Any answer other than `CONFIRM PREVIEW` returns before credential readers and before a client object.
4. Ask for the account identifier with `Account identifier: `.
5. Ask for the token with `API token: `.
6. Keep both values on a `MemoryCredential`. Its text form is `MemoryCredential()`.
7. Send at most two GET requests through `transport.transmit`.
8. Validate, then write only when all three counters are 2.

`--offline` supplies synthetic readers and `SyntheticTransport`. It prints the preview and does not call `input` or a hidden-input function.

`run_live` raises `R55B1_LIVE_NOT_SELECTED` before any prompt or client. A direct `run_session` call with live mode does the same, before the confirmation reader is called. The executable accepts only the built-in `SyntheticTransport`. A class attribute does not admit another class. The real HTTPS and HTTP client classes, and their subclasses, are refused.

Arguments, environment variables, `.env` files, and the Windows credential store are not credential sources. A token placed on the command line is ignored and is not printed. Hidden input does not protect a token from a compromised terminal, a debugger, process-memory inspection, or other software on the machine. The token may still be allowed to trade. That permission remains `UNKNOWN`.
