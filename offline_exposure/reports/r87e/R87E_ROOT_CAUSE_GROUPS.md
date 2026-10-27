# R.87E root-cause groups

These are outcome counts, not independent defect counts or promised recoveries. A guard can block many scenarios; correcting a guard mismatch does not establish downstream behaviour. The UNKNOWN group is an explicitly unresolved investigation queue, not one claimed common cause.

## OBSERVATION_OR_DURABLE_CLOSE_CONTRACT: 21

{'FAILED': 21}. Primary classification: OBSOLETE_BEHAVIOURAL_EXPECTATION.

Mechanism/evidence: Test expects managed adoption/deletion or close booking where current source retains observation-only exposure or requires durable close evidence. Explicit reconciliation refusal/observation log or import helper call and failed managed-book assertion; positions/reconciliation contract inspected.

Recommended action: UPDATE_SUPERSEDED_TEST_CONTRACT. Example: tests/test_broker_exit_accounting.py::test_four_stop_loss_incidents_book_once. Confidence: traceback+source contract.

## HISTORICAL_SOURCE_PIN_DRIFT: 136

{'FAILED': 4, 'ERROR': 132}. Primary classification: HISTORICAL_SOURCE_HASH_ASSERTION.

Mechanism/evidence: A historical/current-baseline raw source digest assertion fails before the intended scenario. Failing _sha comparison in traceback; D15 actual source-only test reproduces the app.py baseline mismatch.

Recommended action: DOCUMENT_HISTORICAL_FAILURE. Example: tests/test_d15_historical_compatibility.py::test_current_protected_hashes_match_d15_baseline. Confidence: traceback-confirmed.

## UNRESOLVED_ASSERTION_OR_BEHAVIOUR: 123

{'FAILED': 123}. Primary classification: UNKNOWN.

Mechanism/evidence: Database cleanup fake returns unexpected initialization/release state; fake cursor/driver contract versus real lifecycle defect needs isolated reproduction. Traceback assertion/exception and source location; parent occurrence recorded separately.

Recommended action: DEFER_PENDING_EVIDENCE. Example: tests/test_d7_resource_cleanup.py::test_t15_t16_t18_failed_initialization_does_not_reuse_or_close_healthy. Confidence: unresolved.

## REMOVED_TEST_PATCH_TARGET: 2

{'FAILED': 2}. Primary classification: OBSOLETE_BEHAVIOURAL_EXPECTATION.

Mechanism/evidence: The test monkeypatches bot_loop.last_account_summary, which is absent in current source; it fails before reaching its intended assertion. AttributeError: 'module' object at forex_bot.bot_loop has no attribute 'last_account_summary'

Recommended action: UPDATE_SUPERSEDED_TEST_CONTRACT. Example: tests/test_decision_repair_f1.py::test_audit_rate_limit_still_records_and_fail_closed_new_exposure. Confidence: traceback-confirmed missing attribute; replacement interface unverified.

## REQUIRED_PERMIT_ARGUMENT_ABSENT: 26

{'FAILED': 26}. Primary classification: MISSING_TEST_FIXTURE.

Mechanism/evidence: Legacy direct adapter calls omit a now-required permission/authority argument and fail at Python argument binding. E           TypeError: _place_market_order_open_sync() missing 1 required keyword-only argument: 'entry_permit'

Recommended action: REPAIR_TEST_FIXTURE. Example: tests/test_execution_headroom.py::test_ordercreate_fill_is_exactly_one_request. Confidence: traceback-confirmed.

## WINDOWS_INTERPRETER_FIXTURE_ON_LINUX: 67

{'FAILED': 67}. Primary classification: PLATFORM_DEPENDENCY.

Mechanism/evidence: Windows interpreter fixture is not an absolute trusted PosixPath; validation refuses before the intended injected scenario. EnvironmentRejected/WorkflowRejected untrusted_executable and inspected select_interpreter/Windows fixture; extracted guard reproduced on Linux.

Recommended action: FIX_PLATFORM_COMPATIBILITY. Example: tests/test_g14_5_security.py::test_inherited_pip_settings_are_not_filtered. Confidence: traceback+source confirmed.

## WINDOWS_HANDLE_OR_CMD_REQUIREMENT: 26

{'FAILED': 26}. Primary classification: PLATFORM_DEPENDENCY.

Mechanism/evidence: Windows WriteFile hook target is None on Linux; the test patches an unavailable API. AttributeError None has no attribute WriteFile; inspected native handle initialization.

Recommended action: FIX_PLATFORM_COMPATIBILITY. Example: tests/test_g14_7_integration.py::test_partial_write_is_not_success. Confidence: traceback+platform-source evidence.

## SOURCE_TEXT_BOUNDARY_ASSUMPTION: 13

{'FAILED': 13}. Primary classification: OBSOLETE_BEHAVIOURAL_EXPECTATION.

Mechanism/evidence: A source-string search assumes a token remains in a particular function; source organisation has changed. ValueError at .index source search; lifespan example reproduced by source fragment without app import.

Recommended action: UPDATE_SUPERSEDED_TEST_CONTRACT. Example: tests/test_live_safety_repair.py::test_lifespan_initialises_before_background_tasks. Confidence: source-chain evidence.

## DNS_REACHED_IN_PURPORTED_OFFLINE_TEST: 1

{'FAILED': 1}. Primary classification: EXTERNAL_SERVICE_DEPENDENCY.

Mechanism/evidence: A DNS resolution attempt reaches the host resolver in a purported offline test. socket.gaierror [Errno -2] traceback; address requests should be blocked by the test boundary.

Recommended action: FIX_TEST_ISOLATION. Example: tests/test_r13_loop_wiring.py::test_g77_no_dns_success. Confidence: traceback-confirmed.

## OPTIONAL_SKLEARN_DEPENDENCY_MISSING: 3

{'FAILED': 3}. Primary classification: IMPORT_OR_COLLECTION_ERROR.

Mechanism/evidence: The test assumes sklearn is available, but the CI environment lacks it; requirements inspected do not declare scikit-learn. Missing sklearn traceback or None library-status assertion; dependency manifest inspection.

Recommended action: REPAIR_TEST_FIXTURE. Example: tests/test_r36_supervised.py::test_libraries_report_missing_lightgbm_without_installing. Confidence: traceback+manifest confirmed.

## READ_ONLY_NUMERICAL_FIXTURE: 1

{'FAILED': 1}. Primary classification: MISSING_TEST_FIXTURE.

Mechanism/evidence: The test mutates a read-only time_ns NumPy view returned by its pandas date-range fixture before reaching the simulator. ValueError output array is read-only at market[time_ns][65:] += ...; _clock uses astype(int64).to_numpy().

Recommended action: REPAIR_TEST_FIXTURE. Example: tests/test_r39_regimes.py::test_a_gap_blocks_entry_and_does_not_open_the_next_signal. Confidence: traceback+fixture-source confirmed; dependency-version causality unverified.

## FROZEN_DATASET_CHECKOUT_EOL: 2

{'FAILED': 2}. Primary classification: PLATFORM_DEPENDENCY.

Mechanism/evidence: Git checkout CRLF conversion changes frozen dataset bytes relative to its pinned LF blob. Expected 3ae3... and actual c6d8... digests; .gitattributes eol=crlf; native Linux sparse checkout byte hashes recorded.

Recommended action: FIX_PLATFORM_COMPATIBILITY. Example: tests/test_r41_structure.py::test_source_hash_constant_and_h1_h4_alignment. Confidence: traceback+Git-byte evidence.

## SHARED_COLLECTION_MODULE_POLLUTION: 11

{'FAILED': 11}. Primary classification: TEST_ISOLATION_DEFECT.

Mechanism/evidence: A clean-import assertion runs in the shared pytest interpreter after other collected tests/fixtures have imported the application. sys.modules membership assertion and inspected operational imports in collected modules/conftest.

Recommended action: FIX_TEST_ISOLATION. Example: tests/test_r5_integration.py::test_h46_application_module_was_not_imported. Confidence: traceback+collection-source confirmed.

## D7_IMPLICIT_IMPORT_FIXTURE: 12

{'ERROR': 12}. Primary classification: TEST_ISOLATION_DEFECT.

Mechanism/evidence: D7 fake installation indexes sys.modules['forex_bot.orders'] although that module has not been imported in the child. Nested traceback at d7_resource_cleanup_runner.py:374, _install_call_fakes.

Recommended action: FIX_TEST_ISOLATION. Example: tests/test_d7_resource_cleanup.py::test_t01_t03_protected_state_aborts_before_resources. Confidence: traceback-confirmed.

## Hypotheses not established

No missing consumed-marker root cause is evidenced in these tracebacks. No production DB outage is inferred from tests using fake drivers. The actual wrapper is present, so removing/migrating it is not a justified fix for the current run. Test-order/random-state effects are candidates, not established per-node root causes. The numerical readonly-array refusal is a fixture mutability failure, not a filesystem permission error. Dataset EOL drift is independently shown by a native Git checkout: blob 3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091 versus checkout c6d8fbf4045d175ead12310cf91eb29b5f5649ded9e0fcbe5b48baf949b09e18.
