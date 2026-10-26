# R.56 phase 3 security boundaries

## What the tests show

- The entry point returns 2 unless the argument list is exactly `--offline`.
- `--live`, `--connect`, `--authenticate`, `--account`, and unknown arguments do not start a session.
- Implementation imports do not include `forex_bot`, `oandapyV20`, `requests`, `httpx`, `urllib`, `socket`, or the trading modules.
- `socket.socket`, `socket.create_connection`, and `socket.getaddrinfo` raise `network_blocked` in the test process.
- Loading the session does not add `requests`, `httpx`, `urllib.request`, `oandapyV20`, or `forex_bot` to `sys.modules`.
- The gate rejects a practice host, an arbitrary host, a non-443 port, `http`, `POST`, a body, redirects, retries, and streaming before any transport call.
- Orders, trades, positions, candles, and unknown paths are rejected.
- A third request and pricing-before-summary are rejected.
- An `approved: true` field cannot skip validation.
- `live_transport()` raises `LIVE_TRANSPORT_NOT_AVAILABLE`.
- Account ids, aliases, bearer text, and exception text are absent from the written JSON.
- Unknown response keys are dropped by the Phase 2 adapters and do not appear in the session file.
- Logs are accepted only under `phase3_offline/synthetic_logs`.
- A failed session writes `SESSION_INCOMPLETE` and does not contain `SESSION_COMPLETE_SYNTHETIC`.
- Repeated sessions create new files and leave an unrelated file unchanged.

## What this does not make safe

The production process is still `DATA_ONLY_MODE_NOT_PROVEN_SAFE`. `main.py` still starts the trading lifespan. `oanda_exec.py` can still call `OrderCreate` and `PositionClose` on the shared production client. This collector is safe because it is a different program, not because the bot gained a data-only mode.

The fixed host name `api-fxtrade.oanda.com` is an allowlist check. No connection to that host is made. The practice host is rejected by this gate. Choosing a practice or live host for a real session needs a later authorisation.

No credential reader exists. No token is read from the environment.
