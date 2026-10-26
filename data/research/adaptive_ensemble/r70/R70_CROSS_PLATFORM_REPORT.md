# R.70 Cross-platform Report

`LINUX_INTEGRATION_NOT_VERIFIED`

## Windows

The offline integration suite ran on the Windows CPython used for this workspace.

- R.70: 26 tests, 0 failures, 7.821s
- R.69: 48 tests, 0 failures, 1 skipped, 4.797s
- R.68: 31 tests, 0 failures, 1 skipped, 0.216s

The harness allows loopback sockets so the Windows asyncio self-pipe can connect. Non-loopback connect and `urlopen` raise `IsolationBreach`. The R.70 suite recorded neither `load_dotenv` nor `socket.connect`.

## WSL2

Command:

```text
wsl -e python3 -B "/mnt/c/Users/Brian/OneDrive/Desktop/Forext Trading Bot 1st/data/research/adaptive_ensemble/r70/poc/test_r70_snapshot.py"
```

- CPython 3.12.3
- Result: `ModuleNotFoundError: No module named 'oandapyV20'` at `forex_bot/reconciliation.py` line 16
- `pandas`: absent
- `numpy`: absent
- `psycopg2`: absent
- `requests`: present

No package was installed. pandas and the OANDA client were not replaced with substitutes. The Linux result is an import failure, not an equivalent integration run, and it is not a VPS result.

## What this does not prove

A passing Windows offline suite does not prove Linux runtime behaviour, PostgreSQL recovery, or broker execution.
