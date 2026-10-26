# STAGE D.3 — STRATEGY ACTIVATION DEFAULTS AND STARTUP SAFETY INTEGRATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: `D3_REMEDIATION_COMPLETE_OFFLINE_TESTED`
- Strategy default status: new `Strategy` objects start inactive. Only an explicit boolean `True` assignment activates one.
- Startup integration status: ordering was reviewed statically. The real lifespan was not run. It still continues into the database, the broker, and background tasks after safety initialization.
- Test outcome: 65 passed, 0 failed, 0 skipped. 35 new tests and 30 Stage D.2 preservation tests.
- Main remaining blockers: lifespan continues after a protected safety file; startup still contacts the broker and the database; the running image does not contain this change; research backtests that assumed the old default will open no new trades.
- Recommended next stage: a separately approved change to `app.py` if startup must stop before broker and database work when safety state is protected. Do not start that stage from this result.

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: none
- Broker mutations: none
- Production database access: none
- Operational-state access: none
- Shadow-mount access: none
- Docker commands: none
- WSL commands: none
- VM commands: none
- Network requests: none
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Not read and not changed.
- Strategy activation: no production strategy was activated.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: the pre-existing dirty tree, including the D.2 `live_safety.py` edit, was left in place. This stage modified `forex_bot/strategy_meta.py` and added the D.3 test and research files.
- Original strategy_meta.py hash: `daffe8ab64cc40016bc337b78da048f10b06314e477f56380bd28f2848995ed1`
- Final strategy_meta.py hash: `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`
- live_safety.py hash: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`
- Unexpected changes: none. `strategy_meta.py` was clean before the edit. `live_safety.py` matched the D.2 hash and was not edited.

## 4. STRATEGY CONSTRUCTION

- Original default: `active = True`
- New default: inactive
- Explicit activation behaviour: assigning boolean `True` still activates. `operator_set_strategy_active` with confirmation still works and can set the strategy inactive again. Authorisation stays BLOCKED.
- Invalid activation handling: `None`, `"true"`, `"false"`, `1`, `0`, empty and nonempty collections, and other objects do not activate. The setter uses `value is True` and does not call `bool(value)`.
- Constructor compatibility: the constructor still takes only `name`. No production caller passed `active=True`.

## 5. STARTUP SEQUENCE

- Module imports: importing the application imports `bot_loop`, which builds the six strategies. They are now inactive. This import was not performed in the tests.
- Strategy construction: `strategy_meta.py` line 77, before lifespan.
- Safety-state initialization: `lifespan` calls `initialise_fail_closed` first among the startup side effects.
- Activation restoration: inside that call, only after the file is classified.
- Database initialization: `get_connection()` after safety init. It connects and applies additive DDL. Not executed.
- Broker initialization: `build_api()` after safety init. Not executed.
- Broker account requests: `fetch_account_summary` after safety init. Not executed.
- Scheduler initialization: `create_task(run_bot())` after safety init. Not executed.
- Background loop startup: reconciliation, health, telegram, and the trading loop are created even when a protected file did not raise.
- Order-routing availability: the live-order gate blocks a new open unless state is valid and authorisation is ALLOWED.

## 6. PRE-VALIDATION ACTIVATION

- Active objects before validation: `NO_PRE_VALIDATION_ACTIVATION_PATH_FOUND_STATICALLY`. Objects exist and are inactive.
- Explicit activation paths: a valid safety document, the confirmed operator setter, and the pytest-only restore helper.
- Remaining activation windows: `bot_loop` skips the `authorised_for_live` check when safety state is not valid. The inactive check still returns first. `allocate_scoped` can name an inactive strategy without setting it active.
- Existing order gate: a BLOCKED or invalid state blocks new exposure.
- Required caller changes: stopping lifespan after a protected file requires `app.py`. Not done.

## 7. D.2 CALLER COMPATIBILITY

- initialise_fail_closed: signature unchanged. Corrupt and future files do not raise, are not overwritten, and do not activate strategies.
- SafetyStateProtected: later writers raise it. A synthetic caller contains it. `evolve` already catches `Exception`. `evolve` was not run.
- Scheduler: not started. Static review shows it starts after safety init even when the file was protected.
- Operator setters: unconfirmed activation does not stick. Confirmed activation still works on a supported file.
- Order-routing gate: a synthetic BLOCKED state raises `RuntimeError` for a new open.
- Remaining integration concerns: the real process and the historical image were not exercised.

## 8. TEST RESULTS

- Tests added: 35 in `tests/test_strategy_activation_defaults.py`
- Tests modified: none. The first T35 assertion matched its own source text and was replaced with an AST check.
- Tests executed: the new file and `tests/test_live_safety_preservation.py`
- Tests passed: 65
- Tests failed: 0
- Tests skipped: 0
- Isolation evidence: pytest temporary safety path; assertions reject `data/ops` and `v2_shadow`; `forex_bot.app`, `forex_bot.database`, and `psycopg2` were not loaded; socket creation during construction and a safety load raises if attempted.
- Model-only tests: T20 through T25 and T31. They call the real safety functions and do not call the real lifespan, broker, or scheduler.
- Untested runtime behaviour: application startup, the trading loop, broker calls, and the production database.

## 9. STARTUP RISK REGISTER

- Confirmed defects: the old constructor default is fixed in source and covered by tests. Lifespan continuation after a protected file remains.
- Resolved defects: construction-time activation.
- Static-only findings: broker, database, scheduler, and shutdown order.
- Remaining high-risk paths: account summary and reconciliation on startup; background loops after a bad safety file; the running image still has the old code.
- Required future changes: an approved `app.py` edit if protected safety state must abort startup before broker and database work. An approved `backtest.py` edit if research backtests must explicitly activate strategies.

## 10. INTEGRATION VERDICT

- Strategy construction: `PASS_OFFLINE_TESTED`
- Activation validation: `PASS_OFFLINE_TESTED`
- Safety-state callers: `PARTIAL`
- Startup ordering: `PASS_STATIC_ONLY`
- Broker ordering: `PASS_STATIC_ONLY`
- Database ordering: `PASS_STATIC_ONLY`
- Scheduler ordering: `PASS_STATIC_ONLY`
- Order routing: `PARTIAL`
- Failure recovery: `PARTIAL`
- Production image: `UNKNOWN`

## 11. DEPLOYMENT BLOCKERS

- Startup blockers: broker account request, reconciliation, and background tasks still follow safety init. A protected file does not stop them.
- Database blockers: live schema compatibility remains unverified. Startup DDL was not executed and was not removed.
- Dependency blockers: unpinned requirements, no lock, no wheelhouse.
- Packaging blockers: no candidate image and no trusted receiving boundary.
- Rollback blockers: no verified rollback target.
- Production-state blockers: container identity, operational state, shadow mount, and the live safety file were not reverified.

## 12. VALIDATION

- Commands executed: git identity and status, hashes, pytest on the two safe modules, ruff on the two touched Python files.
- Files read: strategy construction, lifespan, the bot-loop gate, backtest rebuild, the safety gate, and import headers needed to avoid unsafe imports.
- Files created: the new test module and `data/research/adaptive_ensemble/d3/`.
- Files modified: `forex_bot/strategy_meta.py` only, among production source, in this stage.
- Tests executed: 65 passed.
- Prohibited operations: none.
- Missing evidence: no lifespan run, no live safety-file read, no image rebuild.

## 13. FINAL CLASSIFICATION

`D3_REMEDIATION_COMPLETE_OFFLINE_TESTED`

## 14. NEXT ACTION

- D.3 is complete for the authorised strategy-default change.
- Strategy objects now default inactive.
- All six strategies are covered by tests.
- Startup is not verified safe.
- The bot may not be restarted.
- An image may not be built.
- Production deployment is not authorised.
- Live trading is not authorised.
- A separately approved next stage is required before any startup, image, or deployment work. D.4 was not started.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
