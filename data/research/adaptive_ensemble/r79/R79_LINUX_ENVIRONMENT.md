# R.79 Linux Environment

Evidence class: executed host commands.

| Item | Value |
| --- | --- |
| Host | WSL2 Ubuntu, kernel `6.6.87.2-microsoft-standard-WSL2` |
| Platform string | `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39` |
| Interpreter | CPython 3.12.3 in `$HOME/r79-disposable-venv` |
| SQLite | 3.45.1 |
| Journal filesystem for tests | `TMPDIR=/tmp` (ext4). The repository remains on `/mnt/c` (9p). |
| Production interpreter | Not modified |
| sudo / system packages | Not used |

The virtual environment is outside the repository and outside the Windows production interpreter. `python3 -m venv` created it. Pip installed only `requirements.txt`. No application entrypoint was executed during installation. No `.env` file was read.

Command shape:

```text
python3 -m venv "$HOME/r79-disposable-venv"
"$HOME/r79-disposable-venv/bin/pip" install --disable-pip-version-check --report "$HOME/r79-pip-report.json" -r requirements.txt
```

Operational tests then used:

```text
export TMPDIR=/tmp
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r79/poc/linux_import_audit.py
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r79/poc/test_r79_operational_cycle.py
```
