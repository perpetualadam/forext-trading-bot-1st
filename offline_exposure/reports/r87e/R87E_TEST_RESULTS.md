# R.87E test results

## Actual final executions

- Windows working tree, Python 3.13.5: `python -I -S -B offline_exposure/run_checks.py` — **57 tests, 57 passed, 0 failures, 0 errors, 0 skips**, 0.021s. windows_runner.log.
- Native Linux clean sparse checkout, Python 3.12.3: the same command under a 60-second parent timeout — **57 tests, 57 passed, 0 failures, 0 errors, 0 skips**, 0.020s unittest duration. linux_clean_runner.log; parent wall time 0.098480s.
- Four source-only failure reproductions under a 30-second timeout matched expected exception/refusal outcomes; one additional historical-pin positive control passed. These are NOT five claimed pytest passes. representative_reproductions.json contains exact tracebacks and labels the actual test versus extracted fragments.
- CSV round-trip/uniqueness and 300 FAILED + 144 ERROR totals verified. Workflow structural preservation and no bypass/skip/dependency-install checks passed; git diff --check passed. No YAML/actionlint package was installed or run, and no hosted workflow execution was triggered.

## Exact Linux driver command

```powershell
wsl -d Ubuntu --exec /usr/bin/python3 -I -S -B '/mnt/c/Users/Brian/OneDrive/Desktop/Forext Trading Bot 1st/offline_exposure/reports/r87e/clean_linux_validation.py' '/mnt/c/Users/Brian/OneDrive/Desktop/Forext Trading Bot 1st'
```

The driver performs native Git materialization and runs the isolated child command, then representative_repro.py in the same invocation. Direct reproduction against an earlier /tmp path failed because it was unavailable in the next invocation; no unsupported cause for that disappearance is asserted. The driver now owns fixture lifetime. The initial missing .git/info error was fixed in the disposable harness. One first static check incorrectly included the workflow push key as a job; it was corrected to inspect only jobs. An attempted report JSON patch was rejected before mutation and regenerated through the report serializer. These are tool/harness errors, not hidden product test failures. Earlier successful clean runs were 57/0/0/0; final logs above supersede their timing only.

## Hosted evidence, not rerun here

Current CI: 2,789 passed, 300 failed, 144 errors, 64 skipped, 127 warnings, 62.48s. Parent: same counts, 111.93s. All 444 IDs match, 442 normalized summaries/exception blocks match; two selector values differ. No full application pytest execution was attempted locally. No failing assertion, archive or marker was changed. No commit, push, merge, CI rerun or speculative repair.
