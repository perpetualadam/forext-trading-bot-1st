# R.87F comparison with R.87E

Baseline 9ba819cf1f08b92780a19df5f1d8e54df2c2134d, run 40415275679; new commit a8055c6a9f503a27a8f85d019473f67a3698c3c1, run 40422484155. Comparison uses the actual R.87E CSV (444 unique nodes) and freshly retrieved new job summaries, not aggregate counts alone. ci_comparison.json records the machine-readable comparison.

- Previously failing/error nodes still failing: **444** (300 FAILED, 144 ERROR).
- Previously failing nodes now passing: **0**; every prior node is still explicitly present as a failure/error.
- New failure/error IDs: **0**.
- Prior failure/error IDs missing from the new summary: **0**.
- FAILED/ERROR stage-result transitions: **0**.
- Normalized unchanged summaries: **443 of 444**.
- Raw changed summaries: **9**; eight differences disappear after address/generated-ID/timestamp/whitespace normalization, one does not.

Changed normalized diagnostic:

- tests/test_r21_selector_and_order_state.py::test_12_actual_selector_implementation: R.87E `AssertionError: assert 'swing_mean_reversion' is None`; R.87F `AssertionError: assert 'swing_trend' is None`.

This is a varying result in an existing failing selector test, not a newly failing node. Its causal classification remains unresolved; legacy random selection and shared strategy/flag state are hypotheses, not proven by this comparison. Do not describe the failure logs as identical.

Both full runs reported 2789 passed, 300 failed, 144 errors, 64 skipped and 127 warnings. Current pytest duration 106.80s versus R.87E 62.48s. The same numerical dependency versions appear. All 444 failure/error identities are known, but -q logs do not enumerate every passing/skipped node. Therefore individual identities of all passing/skipped cases, or arbitrary missing/newly collected nonfailing cases, cannot be independently compared from those logs. There is no evidence of changed full-suite collection: existing test code, pytest config and test command are unchanged and reported outcome totals agree. The new separate job intentionally adds 57 hosted offline outcomes; they are not part of the full-suite aggregate.

Masked-regression limitation: historical source guards and setup errors leave downstream application scenarios unexecuted. Equal node sets and a CI-only commit do not prove all application behaviour safe. No assertion, dependency, hash pin or operational function was changed to improve results, and no rerun or repair push followed the failure. The old full suite remains red.
