# Test evidence audit

Current full-suite status: `CURRENT_TEST_STATUS_UNVERIFIED`.

No tests were run in Stage D.1. A passing historical report applies to the tree that existed when that command was recorded. It does not prove this working tree.

## Historical results

| Record | Result | What it covers | Applies to this tree |
| --- | --- | --- | --- |
| Stage brief, earlier baseline | 1,227 passing | Not re-located in the G.7–G.14 JSON opened here | No |
| G.13 `test_results.json` | 239 passed, 3 failed | Safety, provenance, packaging, v2_shadow, and three tests that failed because the Dockerfile had changed | No. Later G.13.1 edited those tests. |
| G.13.1 `test_results.json` | 274 passed, 0 failed | The G.13 set after the three tests were migrated | Not re-run. The three test files are still uncommitted modifications. |
| G.14.6 `test_results.json` | 140 passed | Packaging and wheelhouse security tests | Not re-run. Helpers are untracked. |
| G.14.7 `test_results.json` | 201 passed, 2 skipped | Adds integration tests. Skips are symlink errno 22. | Not re-run. |
| G.14.8 `test_results.json` | 225 passed, 3 skipped | Adds filesystem race tests. | Not re-run. |

G.14.9 through G.14.12 did not run the application suite.

## Evidence classes

`UNIT_TEST_EVIDENCE` exists for live safety, execution safety, decision repair, market provenance, and v2_shadow. The files are `tests/test_live_safety_repair.py`, `tests/test_execution_safety.py`, `tests/test_decision_repair.py`, `tests/test_decision_repair_f1.py`, `tests/test_decision_repair_f2.py`, `tests/test_market_provenance_g5.py` through `g7`, and `tests/test_v2_shadow.py`. Success and failure paths are present in those modules. D.1 did not re-read every test body and did not execute them.

`INTEGRATION_TEST_EVIDENCE` for startup against PostgreSQL or OANDA was not found as an executed nonproduction run. Static tests are not a lifespan run.

`PACKAGING_TEST_EVIDENCE` is the G.13 through G.14.8 scoped pytest recorded above. It checks allowlists, staging, and synthetic wheels. It does not build an image.

`PRODUCTION_COMPATIBILITY_EVIDENCE` is absent. No test read the live safety file, the live database, or the shadow mount.

## Feature gaps

- Startup lifespan: no executed test in this stage. Historical unit tests do not start uvicorn.
- Safety forward compatibility: G.13 recorded the defect from source. A test that proves unknown nested keys survive restart was not identified.
- Database compatibility: no live or fixture migration test was run.
- Rollback: no test.
- Broker disabled: not demonstrated by a startup run.

A test file existing is not a pass. A report of a pass is not a pass of today's uncommitted tree.
