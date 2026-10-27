# R.87E failure classification

Fresh connector reads of the current and parent job logs were parsed independently; the earlier R.87D comparison file was not used as the inventory source. Each of 444 summary nodes maps uniquely to its detailed traceback section: 300 FAILED/call, 144 ERROR/setup, no collection/teardown errors in this inventory. Current and parent node sets match exactly. Both runs: 2,789 passed, 300 failed, 144 errors, 64 skipped, 127 warnings. Current pytest duration 62.48s; parent 111.93s. These are reported hosted results, not local full-suite reruns.

Primary classifications (mutually exclusive, sum 444):

- OBSOLETE_BEHAVIOURAL_EXPECTATION: **36**
- HISTORICAL_SOURCE_HASH_ASSERTION: **136**
- UNKNOWN: **123**
- MISSING_TEST_FIXTURE: **27**
- PLATFORM_DEPENDENCY: **95**
- EXTERNAL_SERVICE_DEPENDENCY: **1**
- IMPORT_OR_COLLECTION_ERROR: **3**
- TEST_ISOLATION_DEFECT: **23**

Previously-present is a separate CSV field, not a root-cause classification. No failure was labelled historical simply because its node also failed previously. Historical hash classification requires a failing digest comparison in the detailed traceback. UNKNOWN entries retain concrete assertions, source locations and investigation hypotheses rather than invented causes. TEST_ORDER_DEPENDENCY is not assigned without a paired order experiment. No missing marker, PostgreSQL outage or source-seal defect is asserted merely from a suggestive file name.

Comparison: 442/444 normalized summaries and exception-line blocks match. Normalization removes memory addresses, generated UUID/32-hex IDs, timestamps and whitespace; 64-character source hashes are retained. Original current/parent assertions and exception excerpts remain in the CSV. Full raw traceback equality is not claimed.

Two differences:

- tests/test_r21_selector_and_order_state.py::test_02_null_selector_blocks: current `AssertionError: assert 'swing_breakout' is None`; parent `AssertionError: assert 'scalp' is None`.
- tests/test_r21_selector_and_order_state.py::test_12_actual_selector_implementation: current `AssertionError: assert 'swing_mean_reversion' is None`; parent `AssertionError: assert 'scalp' is None`.

These are existing failing nodes with varying selector outcomes, not new node regressions. Shared activation state, mode flags and random legacy selection are plausible contributing mechanisms; causality remains unverified. There are zero newly observed failing/error nodes, but failures can mask other regressions and the old job does not exercise the offline coordinator at all.

Inventory fields include node/file, assertion/exception, stage, both commits/results, previous presence, comparison booleans, primary and contributing causes, source locations, excerpts, confidence, safe-offline status, recommendation and job URLs. CSV round-trip verifies 444 unique rows, with exactly 300 FAILED and 144 ERROR entries. Current: https://github.com/perpetualadam/forext-trading-bot-1st/actions/runs/40415275679; parent: https://github.com/perpetualadam/forext-trading-bot-1st/actions/runs/40382545308.
