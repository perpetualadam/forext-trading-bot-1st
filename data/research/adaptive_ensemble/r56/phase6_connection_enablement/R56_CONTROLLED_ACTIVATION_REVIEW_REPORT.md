# R56_CONTROLLED_ACTIVATION_REVIEW_REPORT

Overall: **NO-GO**

This was an activation review. The source gate was not enabled. No OANDA connection was opened. No credential was entered or read. The production bot was not started. Real-session activation still requires a separate operator approval, and the current source is not ready for that approval.

`REAL_SESSION_SOURCE_ENABLEMENT` remains `False`.

## 1. Baseline

The checks below match the current Phase 6 source. They do not by themselves authorise a session.

- `live_session_gate.py` sets `REAL_SESSION_SOURCE_ENABLEMENT = False`. The assignment `REAL_SESSION_SOURCE_ENABLEMENT = True` is absent.
- `real_child_argv()` is `python -B diagnostic_worker.py --authenticated-worker`. That argument list does not contain `--harness-transport`.
- `dispatch_contract("REAL")` sets IPC mode `REAL_SESSION` and capability mode `REAL_SESSION`.
- Issuance uses `mode=contract["capability_mode"]`. Redemption goes through `redeem_for_dispatch`, which calls `assert_dispatch_consistent` and then `issuer.redeem(..., mode=contract["capability_mode"])`.
- `diagnostic_worker.py` does not contain `confirm_one_session`, `issue_runtime_authorisation`, or `ONE_SESSION_PHRASE`. The real child calls `note_parent_ack` only after the parent has written `CAP_OK`, and that function still calls `assert_real_session` before it can construct a grant.
- `issue_offline_mode_binding` records `authorises_network: False`. `issue(mode="REAL_SESSION")` still calls `assert_real_session`. The worker does not call the fixture. `LiveExchange.exchange` requires `assert_real_session` and a `RedeemedCapability` before it constructs `HTTPSConnection`.
- `run_real_session` calls `assert_real_session` on its first statement, before the plan is confirmed, before either prompt, and before `_execute_authenticated_session`. The real spawn path checks the gate again before `Popen`.
- `offline_entry.py` imports `importlib`, `sys`, and `pathlib` only. The Phase 6 implementation modules do not import `bot_loop`, `oanda_exec`, `oanda_client`, `trading`, `execution`, `paper_broker`, `live_broker`, or `load_dotenv`. Phase 5 modules loaded by this entry import the standard library only.

## 2. Launch command

There is no source-defined command that calls `run_real_session`. `diagnostic_supervisor.py` has no `__main__` entry. `offline_entry.launch_authenticated` prints the disabled sentence and returns 2. It does not call the real supervisor.

The only module command, run from `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`, is:

```text
python -B data\research\adaptive_ensemble\r56\phase6_connection_enablement\offline_entry.py
```

This review ran that command with no arguments. It printed:

```text
R56 phase 6 connection enablement is offline. No credential prompt. No network connection.
```

The process exited with code 2. It did not prompt, did not start a child, and did not open a socket.

`python -B data\research\adaptive_ensemble\r56\phase6_connection_enablement\offline_entry.py --offline` is a different command. The source sends it to `run_offline` with the synthetic phrase and a synthetic credential. It is not a real session and it was not run for this review.

`diagnostic_worker.py --authenticated-worker` is the child entry, not the supervisor. With the gate false, that child calls `assert_real_session` and returns 2 before it reads stdin. It was not launched for this review.

No `python -c` invocation, environment override, or test bypass is an authorised launch.

## 3. Fixed request plan

The written request path allows only these two GETs:

1. `GET https://api-fxtrade.oanda.com:443/v3/accounts/{accountID}/summary`
2. `GET https://api-fxtrade.oanda.com:443/v3/accounts/{accountID}/pricing?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF`

Source pins:

- Host `api-fxtrade.oanda.com` and port `443` come from `live_session_gate.LIVE_HOST` / `LIVE_PORT` and from Phase 5 `HOST` / `PORT`.
- `build_tls_context` uses `ssl.create_default_context` and rejects a context unless `verify_mode` is `CERT_REQUIRED` and `check_hostname` is true. An offline check read a local context and confirmed certificate verification is required. No connection was opened.
- `validate_outbound` allows method `GET` only, rejects a body, redirects, retries, streaming, and cookies.
- Paths containing `/orders`, `/trades`, `/positions`, `/transactions`, `/candles`, `/financing`, `/configuration`, `/instruments`, or `stream` are rejected as `ACCOUNT_CHANGING_REJECTED`.
- `SessionBudget.reserve` raises `REQUEST_LIMIT` once two children have started.
- `_execute_authenticated_session` starts pricing only when the summary payload has `error_code` `NONE` and outcome `DIAGNOSTIC_RECORDED`.
- Deadlines above 5 seconds per request or 15 seconds per session raise `DEADLINE_ABOVE_CAP`. The real contract records 5.0 and 15.0.
- The child uses the parent frame's `step`. Summary and pricing are separate children.
- A ready-line timeout or a `communicate` timeout calls `proc.kill()` and then `proc.communicate()`.

These restrictions are in the process that follows this source. They are not an operating-system sandbox. A modified child that ignored `LiveExchange` could open its own socket. The shipped real child does not do that.

The same source also blocks a real token before the socket. `_header_accepted` returns true only for a header that starts with `Bearer SYNTHETIC-` and contains `NOT-REAL`. `LiveExchange.exchange` performs that check before `HTTPSConnection`. A real OANDA token therefore raises `AUTHORIZATION_REJECTED` and does not increment `real_connections_opened`.

## 4. Credential entry

The functions exist and are not reachable while the gate is false.

If a future caller reached them, the order in `run_real_session` would be: source gate, confirmation receipt, `issue_runtime_authorisation`, `prompt_account_id`, then `prompt_hidden_token`. Both prompt functions call `assert_real_session` and `assert_runtime_authorisation` before `input` or `getpass`.

- Account identifier: `input("Account ID: ")`. The typed value is visible in the terminal. It is validated against `^[0-9]{3}-[0-9]{3}-[0-9]{1,20}-[0-9]{3}$`. The synthetic pin and malformed values raise `SYNTHETIC_ACCOUNT_REJECTED` or `ACCOUNT_ID_REJECTED` before a connection.
- API token: `getpass.getpass("API token: ")`. The input is hidden. The value must be 16 to 128 characters and must not contain whitespace. A bad value raises `REAL_CREDENTIAL_USE_NOT_AUTHORISED`.
- `read_environment` and `read_dotenv` raise `REAL_CREDENTIAL_USE_NOT_AUTHORISED` and do not open a file.
- The token is not placed in `argv`. `child_env` copies only safe Windows process keys and removes proxy variables.
- No clipboard API is present.
- After the log write, the parent sets the local account and token names to empty strings and calls `issuer.expire_all()`. That is not a guaranteed wipe of process memory.
- This review did not call either prompt.

## 5. Confirmation

The phrase accepted by `confirm_one_session` is exactly `CONFIRM ONE DIAGNOSTIC SESSION`. The synthetic phrase is rejected. The screen text must contain the live host, `summary`, and `pricing`.

`render_plan` would show:

```text
Environment OANDA LIVE
Host api-fxtrade.oanda.com:443
GET /v3/accounts/{accountID}/summary
GET /v3/accounts/{accountID}/pricing?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF
No orders. No position changes. One diagnostic session.
```

No current command displays that screen. `run_real_session` does not call `input`. It uses a supplied `answer`, a supplied `confirmation`, or a caller-provided `reader`. With neither answer nor reader, the next failure after the gate would be `CONFIRMATION_REJECTED`. While the gate is false, execution stops at `REAL_OANDA_SESSION_NOT_AUTHORISED` and the reader is not called.

`accept_confirmation` spends one in-memory receipt. A second use of the same receipt is `CONFIRMATION_REPLAYED`. Age is taken from the registry, and a receipt older than 60 seconds is `CONFIRMATION_STALE`. The receipt does not by itself set `network_permitted`. The worker cannot mint the receipt. The parent issues and redeems each capability for one session id and one step. Replay, the wrong session, the wrong step, and the wrong mode are rejected. `expire_all` marks the issuer's records spent after a session that reaches the end of `_execute_authenticated_session`.

A new process can create a new receipt. The 60-second receipt is not a durable one-session lock.

## 6. Output inventory

This review created one file:

`data/research/adaptive_ensemble/r56/phase6_connection_enablement/R56_CONTROLLED_ACTIVATION_REVIEW_REPORT.md`

It contains no broker response, account identifier, token, or capability. It is this document.

A future call that got past the gate and finished `_execute_authenticated_session` would create one JSON file:

`data/research/adaptive_ensemble/r56/phase6_connection_enablement/synthetic_logs/r56-phase6-<session id without hyphens>-<four-digit sequence>.json`

`_log_dir` refuses a path outside that directory. The refused real entry raises before `_log_dir`, so a disabled-gate call creates no session file.

If that JSON were written, it would be persisted. Its request rows store endpoint patterns and `body: "NONE"`. `raw_response_persisted` is false. The raw response, raw IPC frame, and parent capability are not fields in the record. Child stderr is discarded. An unexpected child exception becomes `EXCEPTION_CONTAINED` and the exception text is not emitted.

The account summary body stores `account_id_present` as a boolean and `account_id_logged` as false. It can store currency, balance, NAV, margin, and unrealised P/L as diagnostic strings. Pricing rows can store instrument, bid, ask, and spread. Those values are broker-derived. They are the research payload. The parent also rejects the whole record as `SENSITIVE_OUTPUT_BLOCKED` when the exact token, the exact account id, an authorization header, a capability, or an account-id-shaped string is present. An operator can read a passed record without seeing the token or the account identifier.

The current writer cannot honestly label a real session. The session record hardcodes `data_source` `SYNTHETIC_TEST_ONLY`, `confirmation` `CONFIRMED_SYNTHETIC`, and `network_permitted` false. `live_network_access` is copied from the Phase 5 constant `NOT_AUTHORISED`. The child result hardcodes `data_source` `SYNTHETIC_TEST_ONLY` and, on success, `result` `SYNTHETIC_RESPONSE_ACCEPTED`. The parent rejects any other child `data_source` as `MALFORMED_CHILD_RESULT`. Phase 2 stamping is called with `SYNTHETIC_TEST_ONLY`. A real response that reached this writer would be stored under a synthetic label.

## 7. Emergency stop

Practical procedure, if a future standalone diagnostic is in its own console:

1. Press `Ctrl+C` once in that console.
2. Do not treat that key as proof that the children have exited.
3. In another PowerShell window, list processes whose command line contains `phase6_connection_enablement\diagnostic_worker.py` or `phase6_connection_enablement\offline_entry.py`.
4. Stop only those process IDs.
5. Do not run `taskkill /IM python.exe`. Do not stop `main.py`. Do not stop unrelated Python processes.

Source assessment:

- There is no `KeyboardInterrupt` handler and no `finally` that kills `LAST_PROC` or calls `expire_all`.
- The timeout paths do call `proc.kill()` and then `proc.communicate()`, and they close the parent's stdin in the ready-line timeout path. After a normal handshake the parent also closes stdin.
- `expire_all` runs only after the session record is written. An interrupt before that line skips it. The HMAC key exists only in that process, so process exit destroys it. The records are not on disk.
- A timeout that reaches `kill` and `communicate` does not leave that child running. An interrupt that skips those calls can leave the child running.
- A GET that OANDA has already accepted can still finish on the server after the local process dies. Local termination does not send a cancel and does not reverse that request. These two requests are reads. They are not order, trade, or position calls.

Cleanup on `Ctrl+C` is incomplete. That is one reason for **NO-GO**.

## 8. Offline tests

Command:

```text
python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase6_connection_enablement/test_phase6_offline.py
```

Result: **15 passed, 0 failed, 0 skipped, 8.27 s.**

Additional in-process checks, with the gate left false and with `getpass`, `input`, and `Popen` set to raise if called:

- `run_real_session()` raised `GateRejected` `REAL_OANDA_SESSION_NOT_AUTHORISED`.
- The patched prompt and `Popen` callables were not called.
- The real contract tail is `--authenticated-worker`, the harness flag is absent, IPC mode is `REAL_SESSION`, and capability mode is `REAL_SESSION`.
- A harness capability redeemed with the real contract raised `GRANT_REJECTED`.
- An offline `REAL_SESSION` binding redeemed with the harness contract raised `GRANT_REJECTED`. The same binding redeemed with the real contract inside the fixture issuer. `issue(mode="REAL_SESSION")` still raised `REAL_OANDA_SESSION_NOT_AUTHORISED`.
- `LiveExchange.exchange` on a prepared summary, using a non-real synthetic header, raised `GateRejected` `REAL_OANDA_SESSION_NOT_AUTHORISED`. `real_connections_opened` stayed 0.
- The worker text has no self-authorisation phrase and no fixture method.
- The suite's socket patch raises `AssertionError` `network_blocked` for `getaddrinfo`. No OANDA name lookup or HTTPS connection was made.

## 9. Activation change, not implemented

The gate line is `REAL_SESSION_SOURCE_ENABLEMENT = False` in `live_session_gate.py`. Changing that constant to `True` would remain in the file for every later run until a person edits it back to `False`. Nothing in the process writes the constant back. If the process exits, or the machine stops, before that edit, the gate stays true.

That single edit would not produce one controlled session:

- No command calls `run_real_session`.
- A real API token is rejected by `_header_accepted` before `HTTPSConnection`.
- The persisted record would still say `SYNTHETIC_TEST_ONLY`, `CONFIRMED_SYNTHETIC`, and `NOT_AUTHORISED`.
- Confirmation state is in memory for one process and 60 seconds. A second launch could confirm again.
- `Ctrl+C` does not reliably reap the child.

An additional one-session restriction would be required before any future authorisation. This review does not design or add that restriction, and it does not add an environment override or a test bypass.

## 10. Scope that remains unresolved

The two reads, if they were ever authorised and honestly recorded, could supply initial evidence of GBP currency and summary fields, bid and ask prices, observed spreads for the six pairs, response shape, and missing fields. They would not establish GBP pip value, spread-bet stake-to-unit mapping, pip location, home-currency conversion, financing, executable position size, or strategy profitability. No conversion factor is introduced.

## 11. Files and Git

No production file, Phase 2–5 file, or Phase 6 Python file was modified. No previous ZIP was regenerated. No commit, reset, stash, clean, or checkout was run.

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. Before this report, the tracked dirty tree was the same 33 pre-existing names and the porcelain count was 257. This report is a new untracked file.

| File | SHA-256 |
| --- | --- |
| `diagnostic_supervisor.py` | `6556d0273cfa9884a153ec0e72e16ce09c9a691c72844c2a6ace881133f2f14e` |
| `credential_ipc.py` | `77547f55ba5bc038eac04147de76dcdc8ba3701ab0aefe6258ff1a713b54fa4a` |
| `diagnostic_worker.py` | `59afcac36a67ea210699ce8ea91283f8c9e4cb0f5ceef309f0a40a3525078022` |
| `live_session_gate.py` | `ae07d4ca969c8696215510a059e7c5c9e6d66933834b3117080e21207bfeee9a` |
| `restricted_live_transport.py` | `3df6be9b1422ac52f12a8961cc31b079db4b978b6e0ad27f304d1503f5d545e0` |
| `offline_entry.py` | `dc00f6b20efd1c02e4c795aae3f794222c58f71582acc55f25dde6797ff54100` |
| `test_phase6_offline.py` | `360d8101f09cd34f6a8d38eb400167fe0e8a74ea42654ead35571dd629e29ae8` |
| `main.py` | `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb` |
| `forex_bot/oanda_client.py` | `02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a` |
| `forex_bot/oanda_account_adapter.py` | `191466d11e1fac41ef1ccd5603046a3df5c4682f761fde651adcf9229bdf83b5` |

Phase manifests are unchanged: Phase 2 `c1033f885bb956ff0bbcb461291a967d3b0178d46851f37651fc1564e691b441`, Phase 3 `ca0e9707a84646458be24b232a575e3870e8f2de3c6f5746bdb7388cad2fb100`, Phase 4 `6183c33dbec1b334adefa7c2ab663784832cdba806a9a8e99605f26695580b22`, Phase 5 `27026f230e1485e74d462000b6d1d4159a939cd1a500390fc329ea82f8db8cf0`. The Phase 6 manifest remains `972185ff0173d7a01cca5a2187ce816bd910893399029186da03cf85650fa5a6`.

## 12. Blockers

1. No operator command launches `run_real_session`.
2. A real Authorization header is rejected before any socket.
3. Session output is hard-labelled synthetic, and Phase 5 `LIVE_NETWORK_ACCESS` remains `NOT_AUTHORISED` inside the record.
4. Setting the source constant true would persist across later runs. The design has no durable one-session latch and no automatic restoration.
5. `Ctrl+C` does not reliably terminate and reap the child or expire capability records.

## 13. Confirmations

- No real broker connection occurred.
- No credential was entered, requested, or read.
- The production bot remained stopped. `main.py` was not started.
- Real-session activation still requires separate operator approval.
- Source-gate enablement remains **NOT AUTHORISED**.
- Trading remains **NOT AUTHORISED**.
- Production deployment remains **NO-GO**.
