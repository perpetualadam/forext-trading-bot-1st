# STAGE D.5 — ISOLATED ACTUAL-LIFESPAN INTEGRATION AND STARTUP FAILURE VERIFICATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: `D5_ACTUAL_LIFESPAN_ISOLATED_TESTED`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Actual lifespan executed: yes, as `async with forex_bot.app.lifespan(app)` inside a guarded subprocess
- Tests passed: 130
- Tests failed: 0
- Main findings: A valid BLOCKED safety file lets lifespan pass the D.4 guard and call only the installed fakes. Corrupt, future-schema, invalid, unreadable, permission, and failed-write cases raise `StartupSafetyAbort` before any fake database, broker, reconciliation, or background task. Effective authorisation stays BLOCKED. All six strategies stay inactive. A prior successful init does not leave a stale flag that bypasses a later corrupt file.
- Main blockers: production startup is unverified; the running image does not contain the D.2–D.4 bytes; no candidate image, lockfile, or rollback exists.
- Recommended next stage: a separately approved stage. Do not start D.6 from this result.

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: no
- Broker mutations: no
- Production database access: no
- Operational-state access: no
- Shadow-mount access: no
- Docker commands: no
- WSL commands: no
- VM commands: no
- Network requests: no
- Dependency downloads: no
- Package installations: no
- Live-order authorisation: remains BLOCKED in the isolated process; production authorisation was not changed and was not read
- Strategy activation: no production activation; isolated strategies stayed inactive

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty, 56 status lines, 9 tracked modifications. Pre-existing modifications were left in place.
- app.py hash: `f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4`
- live_safety.py hash: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`
- strategy_meta.py hash: `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`
- Unexpected changes: none. The three hashes match the D.2–D.4 expectations. No production source file was edited in D.5.

## 4. IMPORT GRAPH

- Direct imports: FastAPI, config, database, oanda_client, bot_loop, alerts, and the other module-level names listed in `static_import_graph.md`.
- Transitive imports: `bot_loop` pulls `oanda_exec`, `strategy_meta`, and the OANDA endpoint classes. `config` pulls `dotenv`.
- Configuration loading: `load_dotenv()` then `Config` copies the environment. `LIVE_SAFETY_STATE_PATH` is read later, at call time.
- Import-time side effects: `load_dotenv()`, in-memory strategy registry, locks and queues, `FastAPI()` with no listen address. No connect, no thread start, no task start.
- Dangerous dependencies: dotenv, psycopg2, requests/oandapy, lifespan service calls, background tasks, Telegram, order routing.
- Unclassified imports: none left open. Numpy and pandas native init had no network call in the Python package init, and the pre-import socket guard saw no connect during import.

## 5. CONFIGURATION ISOLATION

- Real .env access risk: present in production import, intercepted here.
- Synthetic configuration: installed in a fresh process before import.
- Credential isolation: token variables were empty and were not read from a file.
- Operational path isolation: safety path was a temporary file. `data/ops` is denied by the open guard.
- Shadow path isolation: `v2_shadow` is denied by the open guard and was not used.
- Remaining blockers: the production environment was not read.

## 6. DEPENDENCY REPLACEMENT

- Broker: `build_api` and `fetch_account_summary` were recorders. `requests` raises.
- Database: `psycopg2.connect` raises. `app.get_connection` was a recorder.
- Reconciliation: fake module pre-seeded before lifespan.
- Scheduler: no separate scheduler in lifespan. The reconciliation loop was inert.
- Trading loop: `run_bot` was an inert coroutine. The scheduled code name was `_inner`.
- Telegram: fake `telegram_control`. `app.alert` was a recorder, so the sender thread did not start.
- Background tasks: four inert coroutines. Protected startup created zero tasks.
- Order routing: order, place, and submit callables on `oanda_exec` raise if called. None were called.
- Logging: real `configure_forex_bot_logging` only. Abort text did not include the synthetic document marker.

## 7. ISOLATION GATES

- Gate A result: PASS
- Gate A evidence: static graph, configuration review, and side-effect inventory. `app.py` was not imported for the audit.
- Gate B result: PASS
- Gate B evidence: every isolation-table row is PASS. Guards are installed before import.
- Gate C result: PASS
- Gate C execution evidence: 15 lifespan tests passed. `network` and `fs_denials` were empty. Four scheduled tasks were `_inner`.
- Reason for any blocked gate: none. The first subprocess was stopped because `socket.connect` denied the Windows asyncio self-pipe. That denial stayed in place for every other address. Only `socket.socketpair` may connect, and only to a loopback port bound in that same call.

## 8. TEST RESULTS

- Tests added: `tests/test_d5_lifespan_isolation.py` (15) and `tests/d5_lifespan_runner.py` (script, not collected).
- Tests executed: 130
- Tests passed: 130
- Tests failed: 0
- Tests skipped: 0
- Actual-lifespan tests: T01–T47, 15 pytest functions, all passed.
- Isolated component tests: D.2 preservation, 30 passed; D.3 activation defaults, 35 passed.
- Synthetic model tests: none were labelled as lifespan results.
- Static assertions: D.4 preflight module, 50 passed.
- Tests not run: `tests/test_live_safety_repair.py`, because importing it loads `config` and the real dotenv loader. The full suite was not run.
- Isolation violations: none on the passing run.

Command:

`python -m pytest tests/test_d5_lifespan_isolation.py tests/test_live_safety_preservation.py tests/test_strategy_activation_defaults.py tests/test_startup_safety_preflight.py -q --tb=line`

Result: 130 passed in 4.92s. `PYTHONDONTWRITEBYTECODE=1`.

## 9. SAFETY FLAG LIFECYCLE

- Initial validity: false
- Valid initialization: public flag true, auth BLOCKED
- Corrupt initialization: public flag false, file unchanged
- Future-schema initialization: public flag false, file unchanged
- Repeated initialization: a second protected call still aborts and does not rewrite the file
- Success followed by failure: a corrupt file after a successful init still aborts
- Stale-success bypass possible: no. The public flag was true before that second call and false after the abort.
- Evidence level: ACTUAL_LIFESPAN_ISOLATED

## 10. STARTUP FAILURE BEHAVIOUR

- Protected-state abort: `StartupSafetyAbort` propagates. `initialise_fail_closed` does not raise `SafetyStateProtected`.
- Database calls after abort: zero
- Broker calls after abort: zero
- Background tasks after abort: zero
- Valid BLOCKED startup: proceeds through fakes in the source order and returns
- Shutdown cleanup: fake stop runs; inert tasks are cancelled. The health fake was cancelled before its body ran.
- Partial-start recovery: a failed safety write aborts before database and broker fakes. A failure after those fakes and before `yield` was not injected.
- Untested paths: mid-startup exception after `get_connection`; `tests/test_live_safety_repair.py`; production startup.

## 11. REGRESSION COMPATIBILITY

- D.2: 30 passed
- D.3: 35 passed
- D.4: 50 passed
- Existing repair tests: not run, because they are outside the harness and would import the real configuration loader
- Remaining regression gaps: the repair module, and any test that imports `app.py` without this harness

## 12. REMAINING DEPLOYMENT BLOCKERS

- Startup: isolated only. Production startup is not verified. The running image lacks the D.2–D.4 source.
- Database: live schema unverified. No production connection.
- Dependencies: unpinned requirements, no lockfile, no wheelhouse.
- Packaging: no candidate image, unverified base-image digest, incomplete runtime profile.
- Rollback: no verified rollback.
- Production state: not read. Historical authorisation BLOCKED. Six strategies historically inactive.
- Research compatibility: backtests that skip inactive strategies still need a later explicit activation before they can open trades.

## 13. VALIDATION

- Commands executed: git HEAD, branch, status summary, source hashes, ruff on the two new test files, the pytest command above, and one denied self-pipe diagnostic.
- Files read: the startup modules listed in `validation_log.json`. No `.env`, credential file, `data/ops` safety file, shadow mount, or production database.
- Files created: the two test files and `data/research/adaptive_ensemble/d5/`.
- Files modified: no production source. D.1–D.4 artifacts were not modified.
- Prohibited operations: none.
- Missing evidence: production environment, production safety state, refreshed image identity, and a post-database startup failure.

## 14. FINAL CLASSIFICATION

`D5_ACTUAL_LIFESPAN_ISOLATED_TESTED`

## 15. NEXT ACTION

- D.5 is complete as an isolated lifespan verification.
- Actual lifespan was executed under the harness.
- Isolation was proven for this process: network list empty, filesystem denials empty, fake substitutions in place before use, foreign project path removed.
- Startup safety was verified offline against synthetic files.
- Production startup was not verified.
- The bot may not be restarted.
- An image may not be built.
- Deployment is not authorised.
- Live trading is not authorised.
- Another separately approved stage is required before any deploy, rebuild, or restart.

PRODUCTION DEPLOYMENT: NO-GO.

LIVE TRADING: NOT AUTHORISED.

ROLLBACK: NO-GO.
