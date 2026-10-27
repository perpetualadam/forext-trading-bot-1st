# R.87E executive summary

**R87E_CI_REPAIR_PROPOSAL_PARTIALLY_VERIFIED**. Production remains **NO-GO**. No commit, push, merge, operational edit, marker fabrication or package installation.

The current and parent GitHub runs each report 300 failures, 144 setup errors, 2,789 passes and 64 skips. Fresh log parsing independently matches all 444 failing/error node IDs. Normalized assertion summaries and exception blocks agree for 442; two R21 selector failures report different selected strategies. Equal counts alone were not used to infer identical failures or root causes.

The CSV inventories every node with current/parent diagnostics, stage, evidence, likely cause, classification, confidence, offline-execution status and recommended action. Traceback-supported mechanisms cover 321 outcomes; 123 remain UNKNOWN. All 144 setup errors are explained at their failing boundary: 132 historical hash assertions and 12 D7 missing-import fixture errors. Explaining a blocking guard is not proof that its downstream scenario would pass.

A native, clean, source-only sparse Linux checkout of 9ba819cf1f08b92780a19df5f1d8e54df2c2134d passes the unmodified runner: **57 tests, 0 failures, 0 errors, 0 skips**, Python 3.12.3. The Windows working tree also passes 57/0/0/0. The tracked archive, byte pins, line endings and native permissions were verified without copying local state. Four source-only failure mechanisms were reproduced, including one actual pure historical test.

Prepared a separate offline-exposure-contract job; the existing pytest job is unchanged. The proposed job has not run in GitHub and does not make the repository green. The investigation is partial because 123 causal classifications and full reproductions of unsafe application tests remain open.
