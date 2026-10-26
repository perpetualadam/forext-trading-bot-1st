# R.65 regression report

R.59 through R.64 source was not edited. The R.64 archive still hashes to `c80ce9dc784d5d152fd2d78bfb855d702babe6d90e6473439c0b6725af1af0b5`.

## Windows 11, CPython 3.13.5, pytest 8.4.1

Command, from the project root, with `--noconftest` and `-p no:cacheprovider`:

Before the R.65 files were part of the run, R.59, R.60, R.61, R.62, R.63, and R.64:

96 passed, 13 skipped, 36.42s.

After, the same six trees plus R.65:

107 passed, 13 skipped, 36.75s.

The 11 new passes are the R.65 tests. The skip count is unchanged. No earlier failure appeared.

R.65 alone, before it was folded into the combined run: 11 passed, 0.19s.

## WSL2 Ubuntu 24.04.3, kernel `6.6.87.2-microsoft-standard-WSL2`, CPython 3.12.3, pytest 9.1.1

R.64 and R.65 together: 36 passed, 1 skipped, 2.27s.

R.59 through R.63 were not re-executed on WSL2 in this stage. Their earlier WSL results stay the evidence from those stages. This stage does not invent a new WSL pass for them.

## Not run

`main.py`, network, OANDA, permits, and broker tests were not run.

`R65_NO_OPERATIONAL_CHANGES`
