# R.79 Baseline and Integrity

Evidence class: source inspection and command output. No files were restored from the R.78 archive.

| Check | Result |
| --- | --- |
| HEAD | `d080d897945bc44fa37c02caab504ed707146bec` |
| Branch | `main` |
| Working tree | Dirty. 297 porcelain lines before R.79 edits. 298 after the new R.79 files. Not cleaned. |
| R.78 archive size | 65161 bytes |
| R.78 archive SHA-256 | `c40625eaf4cf027524a506767f5631a7b69e64c0dc0d906be8ab92967a5263bf` |
| R.78 archive members | 35 |
| Manifest mismatches against `R78_SOURCE_HASHES.txt` | 0 before any R.79 edit |

R.78 classification remains `R78_VERIFICATION_PARTIALLY_VALIDATED`. Git HEAD does not by itself identify the dirty R.78 source. The pre-edit manifest match is the baseline.

## Safety gate before executable tests

| Gate | Result |
| --- | --- |
| `REAL_SESSION_SOURCE_ENABLEMENT = False` in r56 phase6, r59, r60, and r61 | PASS. Hashes unchanged. |
| `one_session.permit` | Absent |
| Consumed marker SHA-256 | `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` |
| Marker size | 10 bytes. Contents were not printed. |
| Isolation harness SHA-256 | `b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54` |
| Profit-protection SHA-256 | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |

The same marker, permit, gate, isolation, and profit-protection results were rechecked after the R.79 edits.

## Files changed in R.79

| File | Role |
| --- | --- |
| `forex_bot/startup_recovery.py` | Null epoch and inactive session fail closed for operational publication. |
| `forex_bot/position_recovery.py` | `publish_recovered` requires the fence. `recover_managed_book` uses the offline placer. |
| `forex_bot/entry_capture.py` | Durable finalisation still commits. Memory publication requires the fence. |
| `forex_bot/oanda_exec.py` | OrderCreate and PositionClose re-check recovery authority before permit consumption. |

`entry_journal.py`, `close_journal.py`, `positions.py`, `bot_loop.py`, `trading.py`, `profit_protection.py`, `live_manage.py`, and `broker_close_evidence.py` were not edited. Their hashes match the R.78 baseline.
