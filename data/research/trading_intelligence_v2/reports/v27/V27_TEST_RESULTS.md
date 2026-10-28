# V2.7 focused results — 2026-10-28

Baseline main: 99df373c6ef6b7c711670ef3369024c210747b29.
Windows Python 3.13, isolated -I -S -B runners. No entire historical suite rerun.

- v26d_run.py --native-v27-tests: **63 tests**, 33.032 seconds, exit 0,
  failures/errors/skips 0; synthetic console, local HTTPS, protected native storage.
- v26d_run.py --v27-tests under local Ubuntu /usr/bin/python3: **63 tests**,
  117.204 seconds, exit 0, failures/errors/skips 0; fake console and local HTTPS.
- v26d_run.py --v26g-tests: **67 tests**, 31.725 seconds, exit 0,
  failures/errors/skips 0; verifies the original disabled gate and controller safety.
- v26c_native_check.py --check: **11 checks**, exit 0, no failures/errors/skips,
  no credentials accessed and zero network requests.
- historical_session_entry.py standalone smoke check: expected **exit 2** with
  proposal plus AUTHENTICATED_EXECUTION_DISABLED, no input or dispatch.

The new suite reuses unchanged V2.6E schema and HTTPS lifecycle assertions. Its
13 additional cases cover R.56 prompt/confirmation/two-GET source contracts,
nonexecution and protected permit/marker paths, distinct historical confirmation,
no CLI bypass, hidden non-echo input, backspace, invalid input/Ctrl-C, deadline and
TTY refusal, terminal-to-existing IPC/TLS/publication, timeout fencing without
dispatch, and original V2.3 broker-URL refusal/schema compatibility.

Required checks 1–18: R.56 audited as AST/text only; no diagnostic/source-gate/permit
mutation; original non-account schema/host/GET/M5/MBA/range verified; synthetic
hidden token never appears in output/argv/environment/archive; no trading imports;
write routes/proxies/redirects/foreign hosts refused; no retries after timeout or
error; strict validation plus native atomic/hash/identity publication; wrong-root
OneDrive/repository refusal retained in the G regression; normalized rows match
V2.3 SCHEMA and Bar, while its broker-source prohibition remains intact. All
physical network tests were loopback HTTPS; no OANDA API-host probe occurred.

The terminal/UI-to-controller test uses an explicit synthetic bridge into the
existing controller. The true real-grant branch remains unreachable. Console
objects supply synthetic keystrokes; no real terminal secret is read. This is not
evidence of LIVE support, entitlement, permission or real-token validity.

Snapshot checks compare operational/R.56/frozen research source hashes and
R.56 permit/consumed file metadata before/after. The authorisation refusal,
network adapter, archive/Windows safety code and original test assertions remain
unchanged. Only the dormant controller's exact provider allowlist/deadline call
and runner/CI/frontend files change. No permit is created, consumed or restored.

Final source/marker comparisons passed. V2.6G gate SHA-256 (unchanged raw bytes):
`bfc6ee42f668d703b200a4af065e226e6a6c48bc4a424fe3efd055d9ce704ea1`.
Hosted CI/exact published SHA are provided in the delivery message. Existing
reports are retained as stage snapshots. No synthetic strategy evaluation ran.
