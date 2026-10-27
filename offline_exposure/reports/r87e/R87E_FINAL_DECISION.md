# R.87E final decision

**R87E_CI_REPAIR_PROPOSAL_PARTIALLY_VERIFIED**

Diagnostic inventory and proposed isolated job are reviewable; this is not a green CI or trading decision. All 16 requested deliverables are populated. No commit, push or merge was performed. main remains 9ba819cf1f08b92780a19df5f1d8e54df2c2134d. The workflow patch and reports remain local; no existing operational/test source was altered.

Why does GitHub Actions fail? It collects application/historical/platform tests together. Confirmed blocking mechanisms include 136 source-pin mismatches, 95 platform outcomes, 36 obsolete source/authority/patch-target expectations, 27 fixture defects, 23 shared-import/fake-install isolation defects, three missing sklearn outcomes and one DNS-reaching test. The remaining 123 are explicitly unresolved. These counts sum to 444 failure/error outcomes, not 444 independently established operational defects.

Inherited or new? All 444 failing/error nodes existed in the parent. 442 normalized summaries and exception blocks agree; two selector values differ. There are no new observed failure IDs, but the old workflow never exercised the offline patch and existing failures can mask regressions. Do not call all traces identical.

Can 57 offline tests run independently in a clean Linux environment? Yes: actual native Linux sparse checkout of the exact commit, real tracked archive, repository-applied line endings and Python 3.12.3 yielded 57 passed/0 failures/0 errors/0 skips with no untracked-state dependency. The proposed hosted Actions job has not executed.

Can a separate job be added without hiding the full suite? Yes: the prepared offline-exposure-contract job is additive, least-privilege, dependency-free, bounded and directly propagates runner failure. Original test job/triggers/assertions stay unchanged. Diff and structural checks are recorded.

Smallest justified sequence: review the new job and evidence; separately authorise publication and verify that job at its exact SHA; then repair demonstrated isolation/platform/fixture issues one logical patch at a time while preserving historical pin evidence and every safety assertion; reproduce UNKNOWN groups before operational proposals. Do not treat the new job as a substitute for correcting the still-failing full suite.

Why partial? One actual pure historical test and three extracted mechanisms were safely reproduced; the complete application cases and 123 causes remain unverified. A clean Linux command run is not a hosted job conclusion. Source before/after manifests show workflow alone changed; no safety gates, live permits, consumed markers, credentials, production journals, PostgreSQL or broker operations were accessed/modified by the tests. Any denied availability-probe caveats are documented in the security report.

Stop after R.87E. Do not start recovery fencing or R.88. **PRODUCTION TRADING REMAINS NO-GO.**
