# R.56 Phase 4 transport security

`TARGET_ENVIRONMENT = OANDA_LIVE`

`LIVE_NETWORK_ACCESS = NOT_AUTHORISED`

## Fixed request

- Scheme `https`. `http` is `SCHEME_REJECTED`.
- Host `api-fxtrade.oanda.com`. Port `443`. Any other host or port is `HOST_REJECTED`.
- Method `GET`. Any other method is `METHOD_REJECTED`.
- TLS policy required on the double before the first phase: `verify_mode = CERT_REQUIRED` and `check_hostname = True`. `apply_tls_policy` sets those attributes on an object the caller supplies. It does not import `ssl` and does not wrap a socket.
- Body must be `None`. Redirects must be false. Retries must be `0`. Stream must be false.
- Response body cap `1,048,576` bytes. A larger body is `RESPONSE_TOO_LARGE` and is not parsed or logged.
- HTTP status other than 200 raises `HTTP_{status}` before the body is read, so an error body cannot enter the log.
- The first failed request stops the session. A later request is not sent.
- `seal_live_socket()` raises `LIVE_NETWORK_NOT_AUTHORISED` and does not call DNS or a socket.

## What is not configured

The candidate source does not read `os.environ`, `getenv`, `HTTP_PROXY`, or `HTTPS_PROXY`. There is no proxy setup. There is no arbitrary URL argument. There is no streaming path and no retry loop.

Per-request target: 5.0 seconds. Session target: 15.0 seconds. `SessionClock` rejects a larger budget with `BUDGET_ABOVE_CAP`. These are phase-interface budgets on the offline double. They are not a guarantee for a blocking DNS lookup, a TLS handshake, or a socket read. See `04_timeout_evidence.md`.

## Isolation

`TransportSession` accepts a class named `OfflineDouble` with marker `R56P4_OFFLINE_DOUBLE` and `offline_only is True`. Anything else is `LIVE_TRANSPORT_NOT_AVAILABLE`.

`offline_entry.launch` returns 0 only for the argument list `["--offline"]`. `--live`, `--connect`, `--authenticate`, a token argument, and a missing argument return 2 and write no log. The disabled sentence is:

`R56 phase 4 diagnostic preparation is offline. No credential prompt. No network connection.`

There is no working live CLI and no import of `app`, `bot_loop`, `trading`, `execution`, `oanda_exec`, `paper_broker`, `live_broker`, or `oanda_client`.
