# R.65 portability test report

## Original failure

`data/research/adaptive_ensemble/r64/poc/test_cgroup_probe.py` test `test_this_host_denies_a_private_child_cgroup` asserts `reason == "MKDIR_ERRNO_13"`. Errno 13 is `EACCES`. An independent Linux run returned `MKDIR_ERRNO_30`, which is `EROFS`. Both mean the private cgroup was not created. The archived test treats only errno 13 as the passing denial.

That test was not edited. On this WSL2 host it still matches errno 13, so the R.64 suite still passes here. A host that returns 30 still fails that historical assertion. The portable check is the new R.65 test.

## Correction

`cgroup_denial.py` records the errno it is given and classifies 13 as `EACCES`, 30 as `EROFS`, and 1 as `EPERM`. Any other errno stays `UNCLASSIFIED_OS_ERROR` with that number attached. A missing cgroup file is `FEATURE_MISSING`. A mkdir that succeeds is `PROBE_DIRECTORY_CREATED` after the directory is removed. None of these set `containment_active` or `worker_started`. `refuse_strict` writes no side-effect file.

The R.64 kernel function was not changed. The default policy string remains `REQUIRE_DESCENDANT_CONTAINMENT`.

## Results

Injected cases, Windows and WSL2: errno 13, 30, and 1 each refuse, keep that errno, and create no `side.txt`. Errno 95 stays unclassified and still refuses. A probe with no OS error is not reported as containment.

This WSL2 host's real mkdir is classified `EACCES` with errno 13. Windows reports `UNSUPPORTED_PLATFORM` and does not start a worker.

Windows, CPython 3.13.5: the R.65 file is part of 11 passed in the R.65 directory (0.19s alone). WSL2, CPython 3.12.3: R.64 and R.65 together, 36 passed, 1 skipped, 2.27s. The skip is the R.64 non-Linux case. No worker was launched.

`R65_PORTABILITY_REGRESSION_PASS` for these hosts. An independent `EROFS` machine was not re-run here. The injected errno 30 case is the regression for that result, not a claim that this kernel returned 30.
