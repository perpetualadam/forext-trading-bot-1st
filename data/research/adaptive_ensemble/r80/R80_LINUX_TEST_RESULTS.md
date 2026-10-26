# R.80 Linux test results

Interpreter: the existing `$HOME/r79-disposable-venv/bin/python`, CPython 3.12.3.
Operating system: WSL2 Linux, kernel 6.6.87.2-microsoft-standard-WSL2, x86_64.
`TMPDIR=/tmp` so the journals are on ext4 rather than the 9p mount.
The environment was not modified. No package install.

Command form:

```text
export TMPDIR=/tmp
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r80/poc/test_r80_authorised_concurrency.py
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r79/poc/test_r79_operational_cycle.py
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r78/poc/test_r78_liveness_and_protocol.py
```

| Suite | Result | Runtime |
| --- | --- | --- |
| R.80 | 17 passed, 0 failed, 0 errors, 0 skipped | 16.190s |
| R.79 | 17 passed | 6.282s |
| R.78 | 21 passed | 4.061s |

The R.80 Linux run executed the same multiprocess, fault-injection, recovery-owner, permit, one-cycle, and profit-protection tests as Windows. Synthetic OrderCreate and PositionClose calls occurred inside the fixture. No test contacted OANDA.
