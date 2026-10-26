# R.67C Cross-platform report

The reference model uses `Decimal`, UTC-aware datetimes, explicit snapshot epochs, and `random.Random(67)`. It does not call Windows or Linux process APIs, does not read the environment for trading mode, and does not branch on path separators.

## Runs

| | Windows | Linux via WSL2 |
| --- | --- | --- |
| OS | Windows 11 10.0.26300 | Linux 6.6.87.2-microsoft-standard-WSL2, glibc 2.39 |
| Python | 3.13.5 MSC v.1943 64-bit | 3.12.3 GCC 13.3.0 |
| Command | `python -B -m unittest discover` on `r67/c/poc` | `python3 -B -m unittest discover` on the same directory under `/mnt/c/...` |
| Passed | 70 | 70 |
| Failed | 0 | 0 |
| Skipped | 0 | 0 |
| State-transition differences | none | none |
| Authority-decision differences | none | none |
| Close-decision differences | none | none |
| Final-state differences | none | none |

## Limits

WSL2 is one Linux userland on this machine. It is not a VPS, not a container, and not evidence about cgroup or process-tree behaviour. R.62–R.65 were not run and were not imported.

No platform-specific failure appeared in this model because the model does not touch the platform. That is equivalence of the reference model only.
