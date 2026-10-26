# Gate 2 offline architecture

Gate 2 adds an offline candidate under `data/research/adaptive_ensemble/r55/gate2_offline/`. It does not add a live command, a real credential prompt, or an OANDA connection. Gate 3 remains closed.

The request shape is Option A:

1. `GET /v3/accounts/{accountID}/instruments`
2. `GET /v3/accounts/{accountID}/pricing` with `includeHomeConversions=true`

Host `api-fxtrade.oanda.com`, port 443, GET only, no body, no stream, no retry, no redirect, and no third request. Account summary, orders, trades, positions, transactions, and candles are rejected before a connection object is constructed.

## Components

| File | Role |
| --- | --- |
| `request_gate.py` | Fixed descriptions and the monotonic session clock. A budget above 5.0 seconds per request or 15.0 seconds for the session is rejected. |
| `https_transport.py` | One GET execution against an injected offline double. TLS must be `CERT_REQUIRED` with hostname checks on. The live factory raises `R55G2_LIVE_TRANSPORT_NOT_ACTIVATED` and does not call `getaddrinfo`. |
| `credential_boundary.py` | Preview, exact `CONFIRM PREVIEW`, cancellation, and a synthetic provider. `read_real_credential` raises. Hidden input is `NOT_IMPLEMENTED_GATE2`. |
| `session_controller.py` | Ordered offline sequence. `launch` never calls the session. `run_live` raises `R55G2_LIVE_DISABLED`. |
| `evidence_writer.py` | Structural checks and a sanitised file. The file is written only when both responses validate. |
| `synthetic_test_doubles.py` | Fake connections and synthetic prices. These are not broker facts. |
| `test_gate2_offline.py` | Offline tests. The network fixture is a test safeguard, not a sandbox. |

`run_test_session` is the test entry. It accepts only `SyntheticProvider` and an `OfflineDouble`. It is not a Gate 3 path.

## Sequence

1. Remove any previous `synthetic_output.json`.
2. Show the fixed preview. It names the host, port, two path patterns, `includeHomeConversions=true`, and token permission `UNKNOWN`.
3. Stop unless the callback returns exact `CONFIRM PREVIEW`. No credential is requested.
4. Start the monotonic session clock.
5. A cancel before credentials stops with no credential read.
6. The synthetic provider issues a memory-only handle.
7. A cancel before the first request erases the handle and does not construct a double.
8. Build and validate the two descriptions.
9. Execute instruments. A failure closes the double, skips pricing, and writes no success file.
10. A cancel between the requests skips pricing.
11. Execute pricing only when the session budget is still open and instruments validated.
12. Write the sanitised file only when both validations pass.
13. Erase the handle on every exit.

The CLI prints a disabled sentence and returns. Any argument that starts with `-` returns 2 and does not call `run_live` or `run_test_session`.
