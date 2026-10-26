# Local source and dependency review

This is a local inspection of the B1 session and the research files it loads. It is not an external security audit.

## What is imported

`session_main.py` loads `transport.py` from the B1 directory by its fixed path. `transport.transmit` uses the pinned R.53 connector for request checks and the TLS context. R.53 then loads `r50/connector.py` and `r48/readonly_transport.py` by fixed paths. The offline transport loads `r50/fixtures.py` for synthetic payloads.

Standard-library modules on this path are `hashlib`, `http.client`, `ssl`, `json`, `importlib`, `sys`, and `pathlib`. The session does not import `getpass`. `run_live` raises before any prompt. The offline command does not call input.

## Hash-checked and not imported

R.51 `https_adapter.py`, R.52 `session_entry.py`, R.54 `session_main.py`, and the R.55 Boundary A `session_main.py` are read for their hashes only.

## Inspection

- `transport.py` refuses `HTTPSConnection`, `HTTPConnection`, and their subclasses before it constructs a client. Offline calls use the fixed host, port 443, a five-second timeout, and the verifying TLS context.
- `run_session` accepts only offline mode and only the built-in `SyntheticTransport`. A class attribute is not proof that an arbitrary class is network-free. `run_test_session` is the test-only entry. `launch` and `run_offline` do not call it. `run_live` and `mode="live"` raise `R55B1_LIVE_NOT_SELECTED` before any reader or client. The exact live argument is rejected by `launch` and does not call `run_live`.
- `launch` does not call `run_live`. The exact live argument prints the disabled sentence and returns. An environment variable, a module boolean, a confirmation phrase, or a token added as an extra argument does not select a live session. No arguments print the disabled sentence and return. `--offline` calls `run_offline`, which passes only `SyntheticTransport`.
- Request fields are checked by the pinned R.53 allowlist before a client object is created. Another host, method, path, body, stream flag, or query key raises first.
- There is no subprocess call, no `urlopen`, no `getenv`, and no `forex_bot` import in the B1 session, the transport, or the imported R.53, R.50, and R.48 files.
- `importlib` loads only those fixed paths.
- R.48 has no order-placement function. Its `perform_request` always raises.
- Failures use fixed codes and drop the original message with `from None`.
- Setting `MAX_CALLS = 99` on the loaded connector left the successful session at two calls.
- `transmit` calls `close()` in a `finally` block. The tests observed that close on HTTP failure, timeout, and TLS failure.
- Output is validated before `write_text`. A failed session does not create a file. Offline output is `SYNTHETIC_TEST_ONLY`. The future live label is `READ_ONLY_RESPONSE_NOT_ACCOUNT_VERIFIED`, and `ACCOUNT_VERIFIED` is rejected.

The marker that previously admitted an arbitrary class has been removed from the executable path. The network-denial fixture used by the tests is a testing safeguard, not a general security sandbox. `run_live` is present and raises. It was not executed. This review does not authorise Boundary B2.
