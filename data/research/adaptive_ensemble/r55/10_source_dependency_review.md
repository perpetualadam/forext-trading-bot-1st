# Local source and dependency review

This is a local inspection of the R.55 session and the research files it loads. It is not an external security audit.

## Runtime chain

`session_main.py` checks the four pinned hashes by reading those files. After the preview is confirmed, and only when the client class is not the live HTTPS or HTTP class, it loads `r53/connector.py` from that fixed path. R.53 loads `r50/connector.py` and `r48/readonly_transport.py` from fixed paths. R.51, R.52, and R.54 are hash-checked and are not executed. R.54 is not called because its session asks for credentials before the preview. The preflight script and the test file are not imported by the session.

## Inspection

- The four runtime files contain no subprocess call, no `urlopen`, no `getenv`, no `getpass`, no `.env` loader, and no `forex_bot` import.
- `importlib` is used only to load the pinned R.53 file. There is no dynamic import of a caller-supplied name.
- There is no call that constructs `HTTPSConnection`. The session and R.53 both refuse that class, `HTTPConnection`, and subclasses before use.
- Request fields are checked against a fixed set. Another host, method, path, body, stream flag, or query key raises before a client object exists.
- The only result writer is R.53 `write_clean`. It validates the allowlist before `write_text`. `run_session` calls it only when all three counters are 2.
- Failures use fixed codes. Replacement exceptions drop the original message with `from None`.
- R.48 has no order-placement function. Its `perform_request` always raises. The session never calls a production order client.
- The network modules on this path are the standard-library `http.client` and `ssl` modules inside the pinned connector. They are used to refuse the live class and to build a verifying TLS context. The offline run supplies a fake client class.
- Setting `MAX_CALLS = 99` on the loaded connector left the successful session at two calls. The loop is the fixed pair of endpoint names.
- `transmit` calls `close()` in a `finally` block. The tests observed that close on HTTP failure, timeout, and TLS failure.
- `launch` and `main` print the disabled sentence and return. They do not call `run_session`. `enable_live` and `future_live_entry` raise `R55_LIVE_TRANSPORT_DISABLED` immediately.
- A confirmation answer is not stored. Any answer other than the exact preview confirmation returns before credential readers and before a client object.

## Injection point

`run_session` accepts a connection class so the offline test can replace the network boundary and still run the real connector. That parameter is not reachable from the default command, from an argument, from an environment variable, from a confirmation phrase on the command line, or from a module boolean. The live client classes remain refused. A later live program has to be a new file, or a change that produces a new SHA-256, and it still needs a separate written approval.

No unresolved finding is carried as a blocker.
