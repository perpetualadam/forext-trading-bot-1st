# R56_REAL_DISPATCH_CORRECTION_REPORT

Overall: **PASS**

`REAL_SESSION_SOURCE_ENABLEMENT` remains `False`. No OANDA connection was opened. No real credential was read. The production bot was not started.

Real network execution was not tested: `REAL_NETWORK_EXECUTION_NOT_TESTED`.

## Files changed

- `diagnostic_supervisor.py`
- `credential_ipc.py`
- `test_phase6_offline.py`
- `01_architecture.md`
- `03_timeout_and_ipc_evidence.md`
- `04_test_results.md`
- `05_future_one_session_procedure.md`
- `06_integrity_manifest.json` (regenerated after this report)
- `10_real_dispatch_correction.md` (this file)

`diagnostic_worker.py`, `live_session_gate.py`, `restricted_live_transport.py`, and `offline_entry.py` were not modified. No new Python module was added. Phases 2–5 and production sources were not modified.

## Root cause

`run_real_session` called `run_authenticated_harness_session(..., live=False)`. That path always launches `--authenticated-worker --harness-transport` and writes IPC mode `AUTHENTICATED_HARNESS`. A future change of the source switch would still have dispatched the synthetic harness.

## Correction

`run_real_session` now checks the source switch before the plan, the confirmation, the prompts, and any worker. The statements after that check call `_execute_authenticated_session(dispatch_mode="REAL")`. They do not call `run_authenticated_harness_session`. `run_authenticated_harness_session` hardcodes `dispatch_mode="HARNESS"` and has no parameter that can select the real worker.

`REAL` dispatch uses `real_child_argv()`, IPC mode `REAL_SESSION`, authorisation kind `REAL_SESSION`, and `CapabilityIssuer.issue(..., mode="REAL_SESSION")`. That issue call checks the source switch again before a token exists. `_spawn_authenticated` also checks the source switch before `Popen` when the mode is `REAL`. `HARNESS` dispatch keeps the harness argv, `AUTHENTICATED_HARNESS` frames, and `HARNESS_SESSION` capabilities. `assert_dispatch_consistent` rejects a real IPC mode paired with `--harness-transport`, and the reverse mixture. `authenticated_frame` rejects a harness authorisation kind on a `REAL_SESSION` frame.

## Verification labels

- `REAL_DISPATCH_CONTRACT_VERIFIED`: `dispatch_contract("REAL")` returns `--authenticated-worker` with no harness flag, IPC mode `REAL_SESSION`, capability mode `REAL_SESSION`, budget 2, request deadline 5 seconds, and session deadline 15 seconds. The real worker process was not started.
- `SHARED_SUBPROCESS_FLOW_VERIFIED`: `run_authenticated_harness_session` still runs the two fake GETs, the summary-failure stop, and the kill-and-reap timeout through `--harness-transport`.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`: no real DNS, socket, or HTTPS call was made, and the real worker argv was not executed.

## Worker self-authorisation

`diagnostic_worker.py` still does not contain `confirm_one_session`, `issue_runtime_authorisation`, or the confirmation phrase. A harness child with no capability returns `GRANT_REJECTED`. A forged token answered with `CAP_NO` returns `CAPABILITY_REJECTED`. `note_parent_ack` still raises `REAL_OANDA_SESSION_NOT_AUTHORISED` while the switch is false. A harness grant still fails `assert_parent_capability`.

## Tests

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase6_connection_enablement/test_phase6_offline.py`

**14 passed, 0 failed, 0 skipped, 7.38 s.**

The hang case remained `CHILD_TERMINATED`, one child, pricing `NOT_SENT`, and `SESSION_INCOMPLETE`, with wall time at least 0.5 seconds and below 8 seconds. `LAST_PROC.poll()` was not `None`. Summary status 500 did not start pricing. A third budget reservation returned `REQUEST_LIMIT`. The account id, synthetic token, and capability text were absent from argv, the child environment, and the session logs.

## Limitations

- The source switch is still false, so the real worker is not started and a real socket cannot be opened.
- The dispatch contract proves the command, IPC mode, capability scope, budget, and deadlines. It does not prove a live HTTPS exchange.
- A parent capability is not OANDA authentication and it is not an operating-system sandbox.
- Killing a child does not cancel a GET a server has already accepted. No such GET was sent.
- GBP pip value, stake-to-unit mapping, pip location, home-currency conversion, financing, executable sizing, and strategy profitability stay unresolved. No `1.35` conversion was introduced.

## Source hashes

- `restricted_live_transport.py` `3df6be9b1422ac52f12a8961cc31b079db4b978b6e0ad27f304d1503f5d545e0` (unchanged)
- `credential_ipc.py` `77547f55ba5bc038eac04147de76dcdc8ba3701ab0aefe6258ff1a713b54fa4a`
- `live_session_gate.py` `af6db5c62d934a9ab38076d7114e0e83c1b6e67f7ed0ec1d88e36bad60fc8bc6` (unchanged)
- `diagnostic_worker.py` `59afcac36a67ea210699ce8ea91283f8c9e4cb0f5ceef309f0a40a3525078022` (unchanged)
- `diagnostic_supervisor.py` `88e106ce54a8ba547d182c3c3a08d735cad952d01df39b8973945989c0c50f22`
- `offline_entry.py` `dc00f6b20efd1c02e4c795aae3f794222c58f71582acc55f25dde6797ff54100` (unchanged)
- `test_phase6_offline.py` `ad1eea1886285c581c297c9d416989abe8fb8ac4bafc94fd08736c2847f38d1d`

## Git integrity

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. No commit, reset, clean, stash, or checkout was run.

## Confirmations

- Real activation remains disabled.
- No real credential was entered, read, or requested.
- No OANDA Live or Practice connection was made.
- The production bot remained stopped.
- Production deployment remains NO-GO.
