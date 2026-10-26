# R56_ONE_SESSION_ACTIVATION_PREPARATION_REPORT

Overall: **PASS**

Real activation remains disabled. `REAL_SESSION_SOURCE_ENABLEMENT = False`. No OANDA connection was opened. No real credential was read. The production bot was not started.

## Files changed

- `restricted_live_transport.py`
- `credential_ipc.py`
- `live_session_gate.py`
- `diagnostic_worker.py`
- `diagnostic_supervisor.py`
- `test_phase6_offline.py`
- `01_architecture.md`
- `02_request_and_credential_security.md`
- `03_timeout_and_ipc_evidence.md`
- `04_test_results.md`
- `05_future_one_session_procedure.md`
- `07_phase6_report.md`
- `06_integrity_manifest.json` (regenerated after this report)
- `08_one_session_activation_preparation.md` (this file)

`offline_entry.py` was not modified. No new Python module was required. Phases 2–5 and production sources were not modified.

## The four blockers

1. `diagnostic_worker.py` no longer rejects every authenticated entry before it can run. Bare `--authenticated-worker` still checks the source switch and returns `REAL_OANDA_SESSION_NOT_AUTHORISED` before it reads stdin. `--authenticated-worker --harness-transport` is the same worker with a fake connection and an HTTPS tripwire. After a future source-gate change, the same function continues into `consume_real`, `LiveExchange`, and the runtime grant.
2. `live_session_gate.py` can mint a `RuntimeGrant` only after `assert_real_session()` succeeds, the operator confirms `CONFIRM ONE DIAGNOSTIC SESSION`, the host is `api-fxtrade.oanda.com`, and the plan is the two approved GETs. While the source switch is false, `issue_runtime_authorisation()` raises `REAL_OANDA_SESSION_NOT_AUTHORISED` and returns nothing.
3. `prompt_account_id` and `prompt_hidden_token` call both gates before terminal input or `getpass`. `consume_real` checks the source switch before it parses a frame. The harness child reads one schema `r56.phase6.ipc.2` frame. A `REAL_SESSION` descriptor on that frame is refused.
4. `LiveExchange.exchange` passes the caller grant into `assert_runtime_authorisation`. It no longer passes `None`. The harness branch requires a `HarnessGrant` and never calls `HTTPSConnection`.

## Additional finding

Phase 3 still accepts only the synthetic account pin `001-001-0000000-001`. A non-synthetic id is validated and substituted inside Phase 6. That is a reuse limit, not a new activation blocker. No other concrete blocker was found in the authenticated path.

## Parent-to-child flow

`run_authenticated_harness_session` checks confirmation before it calls the credential source. A wrong answer raises `CONFIRMATION_REJECTED` and the source is not called. Deadline and log-path checks also happen before the source. The source returns one synthetic account id and one synthetic token in memory. The parent validates the account id, writes one bounded frame to the child stdin, and closes the pipe.

The child is `diagnostic_worker.py --authenticated-worker --harness-transport`. It installs a tripwire on `HTTPSConnection`, reads one frame, closes stdin, checks the harness descriptor, builds a `HarnessConnection` from the fixture, mints a local `HarnessGrant`, selects `LiveExchange`, runs the assigned GET, emits an allowlisted record, expires the grant, and exits. The parent runs the Phase 2 adapters on that record, writes the allowlisted session log, and scans the log for the exact account id and token. A summary error other than `NONE` does not start the pricing child.

Bare `--authenticated-worker` and `prepare_real_session` stop at the source switch. They do not read credentials and they do not open a socket.

## Runtime authorisation

`RuntimeGrant.authorises_network` is true and can be created only by `issue_runtime_authorisation` after the source switch. `HarnessGrant.authorises_network` is false. The synthetic phrase `SYNTHETIC OFFLINE CONFIRM` cannot mint either grant. Grants are session-specific and step-specific. `expire_grant` marks them spent. A spent, missing, or wrong-step grant is rejected before `HarnessConnection.perform`. The grant is not stored, is not read from the environment, and is not accepted from an undocumented flag.

A parent-issued descriptor is not a secret and is not server-side authorisation. A forged harness descriptor can drive only the fake connection. A forged real descriptor cannot pass `assert_real_session`. Object identity does not cross the pipe; the child re-issues a local harness grant after the descriptor checks.

## Credential prompting and IPC

Account id is terminal input. The API token is `getpass`. Both prompts sit behind the source switch and a runtime grant, so this task never displayed them. Tests replaced `input` and `getpass` with functions that fail if called. The call count stayed zero.

The harness frame is one JSON object, at most 262144 bytes, schema `r56.phase6.ipc.2`, mode `AUTHENTICATED_HARNESS`. The account id is validated before the path is built. The token stays in the sensitive set and is cleared after the step. The parent closes stdin after one write. Child stderr is discarded. Exact account id and token values are absent from argv, the public IPC copy, the session log, and parent stdout.

## How the transport receives the grant

`RestrictedLiveTransport` stores the grant given to its constructor. `_finish` passes that object as the third argument to `exchange`. On the harness path, `assert_harness_authorisation` runs before `perform`. On the real path, `assert_real_session` runs first and `assert_runtime_authorisation(grant, session_id=..., step=...)` runs before `real_connections_opened` is incremented and before `HTTPSConnection`.

## Two-GET enforcement

The child built `/v3/accounts/{accountID}/summary` with an empty query and `/v3/accounts/{accountID}/pricing` with only `instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF`. The test compared SHA-256 of those paths and of the canonical query. It did not put the raw path in the child JSON. Invalid account ids still fail in `build_prepared` before a connection opens. A third request on the same transport returns `REQUEST_LIMIT`. Account-changing methods and endpoints, redirects, and retries remain rejected. TLS context stays `CERT_REQUIRED` with hostname checks. `LiveExchange.real_connections_opened` stayed 0.

## End-to-end subprocess evidence

`test_authenticated_child_process_runs_the_two_gets` called `run_authenticated_harness_session`, which launched the real worker module as a child process. The successful session recorded `SESSION_COMPLETE_SYNTHETIC`, two children, `LiveExchange`, `grant_checked` true, and `real_connections_opened` 0. Account diagnostics were GBP, balance 100.00, NAV 100.00, margin available 100.00, margin used 0.00. EUR_USD bid 1.10000, ask 1.10020, calculated spread 0.00020. Summary status 500 recorded `HTTP_500`, one child, and pricing `NOT_SENT`.

The fake response was injected through `HarnessConnection`. The child tripwire replaces `http.client.HTTPSConnection`. The test process also blocks `socket.socket`. No real DNS, socket, or HTTPS call was made.

## Offline test counts

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase6_connection_enablement/test_phase6_offline.py`

**13 passed, 0 failed, 0 skipped, 6.98 s.**

## Timeout and cleanup

The hang case used `stall=hang` on the summary child and `request_deadline=0.5`. The parent recorded `CHILD_TERMINATED`, `child_alive` false, `child_termination` `TERMINATED`, one child, pricing `NOT_SENT`, and `SESSION_INCOMPLETE`. Observed wall time was at least 0.5 s and below 8 s. `LAST_PROC.poll()` was not `None`. The existing caps still reject a request deadline above 5 s and a session deadline above 15 s. A timed-out request is not retried.

## Sanitised synthetic output

```text
session_status: SESSION_COMPLETE_SYNTHETIC
children_started: 2
exchange: LiveExchange
grant_checked: true
real_connections_opened: 0
account.home_currency: GBP
account.balance: 100.00
account.nav: 100.00
account.margin_available: 100.00
account.margin_used: 0.00
pricing[0].instrument: EUR_USD
pricing[0].bid: 1.10000
pricing[0].ask: 1.10020
pricing[0].spread_price: 0.00020 (BOT_CALCULATED)
executable_order: NOT_PRODUCED
gbp_pip_value: GBP_PIP_VALUE_UNVERIFIED
live_network_access: NOT_AUTHORISED
network_permitted: false
real_session_source_enablement: false
```

Broker-reported fields are the account figures and the bid, ask, and instrument. The spread is calculated. GBP pip value, stake-to-unit mapping, pip location, home-currency conversion, financing, executable sizing, and strategy profitability stay unresolved. No `1.35` conversion was introduced. The API token is not reproduced in this report.

## Remaining risks

- The source switch is still false, so a real session cannot start.
- `--harness-transport` is a documented test seam. It tripwires HTTPS and cannot authorise `HTTPSConnection`. It is not an operating-system sandbox.
- A parent grant or IPC descriptor does not authenticate the process to OANDA.
- Killing a child does not cancel a GET that a server has already accepted. No such GET was sent.
- Prompts and `consume_real` are implemented and unexecuted. They run only after the source switch and a runtime grant.
- Phase 3 cannot validate a non-synthetic account id. Phase 6 does that validation itself.

## Source hashes

- `restricted_live_transport.py` `feba041cbde02a4cbb8454b489da73c5d5fd9ee562b04b04c24868a04eeabe86`
- `credential_ipc.py` `669c820084e2e8a14f695a48b3ae52aceb7b0e36afd65034bccdb8c8267ecb46`
- `live_session_gate.py` `46f614219981a68825ed1176badc6df37a27cfe09c30bb9af2b761446ea81f1d`
- `diagnostic_worker.py` `5aeda8ebccdf269e1c730755cdb89af49c6577c4e6fb34bea9b594d9d5f61d42`
- `diagnostic_supervisor.py` `aebd77b7be2c45be5136336c465b8dcce56090b4108129e9fc20b5b7d52eb0b3`
- `offline_entry.py` `dc00f6b20efd1c02e4c795aae3f794222c58f71582acc55f25dde6797ff54100` (unchanged)
- `test_phase6_offline.py` `75a023ff9fbcefcb10a4b3210060b8407785326f98681aeeb9b1033bd1b3a43f`

## Git integrity

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. Porcelain count at the start of implementation was 257. No commit, reset, clean, stash, or checkout was run.

## Confirmations

- `REAL_SESSION_SOURCE_ENABLEMENT` remains `False`.
- No real credential was entered, read, or requested.
- No OANDA Live or Practice connection was made.
- The production bot remained stopped.
- Production deployment remains NO-GO.
