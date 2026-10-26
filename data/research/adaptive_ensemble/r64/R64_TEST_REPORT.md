# R.64 test report

## Baseline, before R.64 code

| Check | Result |
| --- | --- |
| `R63_POC_SOURCE_REVIEW.zip` | 18837 bytes, SHA-256 `046f769a9a40394de6a378354905b74e714be6635529d276cf13d96aaaf736a8` |
| Nine R.63 members | All matched |
| R.63 on Windows 11 10.0.26300, CPython 3.13.5, pytest 8.4.1 | 14 passed, 6 skipped, 9.05s |
| R.63 on WSL2 Ubuntu 24.04.3, kernel `6.6.87.2-microsoft-standard-WSL2`, CPython 3.12.3, pytest 9.1.1 | 8 passed, 12 skipped, 3.77s |
| R.56, R.59, R.60, R.61 gates | `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| Consumed marker | 10 bytes, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` |
| Permit | Absent |

`R64_BASELINE_VERIFIED`

## R.64 commands

Windows:

```text
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r64\poc -q --tb=short
```

23 passed, 3 skipped, 0.11s. The skips are the Linux mount checks.

WSL2, `$HOME/r60pytest`:

```text
"$HOME/r60pytest/bin/python" -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r64/poc -q --tb=short
```

25 passed, 1 skipped, 1.78s. The skip is the non-Linux probe check.

No `r64-*` directory remained under `/sys/fs/cgroup/init.scope`. No `synthetic_worker.py` or `time.sleep(60)` process remained. No harness kill of a survivor was required, because the real tests did not fork.

## Real and simulated

Real, both hosts: the probe reports `kernel_containment` false and `delegated` false. Strict open does not fork and writes no worker file.

Real, WSL2 only: mkdir errno 13, `init.scope` not writable, `cgroup.procs` and `cgroup.kill` present, effective capabilities zero, three probes leave no child, and a kill request for that current cgroup is refused.

Simulated, both hosts: 14 fault names. Each result has `evidence` `SIMULATED` and `kernel_containment` false. Owner crash after release stays `CLEANUP_INCOMPLETE`. A direct kill with a living grandchild is not descendant containment. The explicit direct-child record is not equivalent to full containment.

`run_contained` was not entered. There is no passing test of placement, inherited membership, `cgroup.kill`, or cgroup removal.

## Unverified

- Kernel descendant containment on Linux.
- Owner crash against a real populated cgroup.
- Windows Server, Debian, VPS, Docker, and other OCI runtimes.
- Cancellation of a blocked `CreateProcess` or `fork`.

`REAL_NETWORK_EXECUTION_NOT_TESTED`.

The stage label is `R64_POC_INCOMPLETE`.
