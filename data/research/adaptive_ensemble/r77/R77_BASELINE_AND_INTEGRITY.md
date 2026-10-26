# R.77 baseline and integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main` was verified before editing and was unchanged at the end of the stage. The working tree was already dirty. It was not reset, stashed, cleaned, or committed. `git status --porcelain` reported 294 lines after the R.77 files were added.

Every expected R.76 baseline hash matched before editing. After editing, these files still match that baseline:

- `forex_bot/broker_entry_evidence.py`
- `forex_bot/oanda_exec.py`
- `forex_bot/positions.py`
- `forex_bot/trading.py`
- `forex_bot/broker_close_evidence.py`
- `forex_bot/broker_exit.py`
- `forex_bot/broker_protection.py`
- `forex_bot/live_manage.py`
- `forex_bot/profit_protection.py` `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`
- `forex_bot/execution.py`
- `forex_bot/reconciliation.py`
- `main.py`

`one_session.consumed` remains 10 bytes with SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`. The body was not printed. No `one_session.permit` file exists.

Source gates still contain `REAL_SESSION_SOURCE_ENABLEMENT = False`:

- phase 6 gate `75a2031a5dd199996eec0b533cf4a83b44362d366fad65ff3585b8151bc18cac`
- R.59 and R.60 gate `2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2`
- R.61 gate `2f89959f8cae0e45589b16d159f038af370aa9cec592455784046ef57230c4c0`

R.76 schema was version 3 with partial index `one_unresolved_entry`. Current `SCHEMA_VERSION` is 4 (`forex_bot/close_journal.py` line 31). `open_journal` (lines 787–802) still refuses a missing file, an empty file, a failed integrity check, and any version other than 4.

`execute_startup_sequence` (`forex_bot/startup_recovery.py` lines 148–247) still runs before `live_management_permitted` can become true. The live branch in `_evaluate_impl` (lines 796–802) returns when that function is false. The R.75 close path still requires `CloseSubmissionPermit` before any close request (`forex_bot/oanda_exec.py` lines 401–414). Profit-protection constants were not edited.
