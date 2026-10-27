# R.87D final decision

**R87D_MAIN_UPDATED_CI_NOT_VERIFIED**

The reviewed offline correction was committed and safely fast-forward pushed to GitHub default main: `9ba819cf1f08b92780a19df5f1d8e54df2c2134d`. Exact scope: three offline coordinator/test/runner files plus their separately reviewed new pure dependency forex_bot/exposure_view.py. No existing operational trading file was modified. The index is empty; scheduler modifications, proposal, reports and other unrelated work remain local/uncommitted. One commit was created; no history rewrite or force-push.

Repository root: C:/Users/Brian/OneDrive/Desktop/Forext Trading Bot 1st. Current branch main. Local HEAD, origin/main and GitHub main were independently verified at `9ba819cf1f08b92780a19df5f1d8e54df2c2134d`. Parent was 883752f91510f639d354f090331446dcc6ade0a8. R.87B reference 529277b is that parent's parent and contains the same wrapper. Accessible local refs/worktrees do not contain the reported uncommitted sealed restoration. Cloud patch transfer is absent; no evidence of a committed restoration later reintroduced locally.

Current bot_loop SHA-256 remains 2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d. Required sealed R.86 hash remains a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81. The archive matches that seal. Wrapper restoration and six-test migration were excluded and await separate verified compatibility work and approval. The existing offline mismatch-evidence test also needs separate transparent review if the wrapper is restored. No seal assertion changed.

Local isolated tests: concurrency 10 passed, complete 57 passed, historical 48 passed; every run had 0 failures, 0 errors, 0 skips. Raw code/staged hashes are recorded in staged_manifest.json, source_before.json and source_after.json; all four match supplied expected hashes, and all ten operational comparison sources plus six compatibility files stayed unchanged through tests/commit/push.

GitHub Actions completed for this exact SHA but **failed**: 300 failures, 144 errors, 2789 passed, 64 skipped. The parent has identical failure/error node sets and summary counts. No configured required checks are advertised, and offline coordinator CI coverage is missing. Thus there is no completed-successful-CI claim. Refer to R87D_CI_RESULTS.md for exact workflow/job URLs and investigation evidence.

Direct answers:
- Was the offline coordinator correction safely committed to GitHub default main? Yes, within the explicit four-file reviewed offline scope.
- Does GitHub Actions show completed successful required checks for that exact commit? No. The CI job failed, no protected required contexts were advertised, and the offline suite is not covered.
- Were all existing operational trading files preserved? Yes; no operational caller, strategy, sizing, SL/TP, profit protection, weekend flattening, gate, permit or marker change was made. The new pure module has no production callers.
- Is the R.87B wrapper correction included? Excluded; still awaiting separate compatibility verification and approval.

Remaining blockers: broad CI baseline failures, missing isolated coordinator CI workflow, untransferred cloud changes, sealed-wrapper/consumer disagreement, and production evidence/freshness/coordinator gaps. No CI repair, operational restoration, production integration, R.87 recovery or R.88 was started. Stop here. **PRODUCTION TRADING REMAINS NO-GO.**
