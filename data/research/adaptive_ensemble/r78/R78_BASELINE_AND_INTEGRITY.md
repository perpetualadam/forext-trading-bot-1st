# R.78 baseline and integrity

Checked before operational edits.

| Item | Result |
| --- | --- |
| HEAD | `d080d897945bc44fa37c02caab504ed707146bec` |
| Branch | `main` |
| R.77 archive size | `100010` bytes |
| R.77 archive SHA-256 | `b0eab11afeeb780acb7aa0abbbbe5f56121e04105871ec7b5025ce788dea68e4` |
| Consumed marker SHA-256 | `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` |
| Marker size | 10 bytes, contents not printed |
| `one_session.permit` | absent |
| Expected operational hashes | 0 mismatches |

The working tree was already dirty. It was not cleaned.

After the R.78 edits, these files still match the R.77 baseline:

- `forex_bot/entry_journal.py` `aea5b74e0f431a90b1bd410d650295a5b79d4d901f77391234cd9ddaa5653a07`
- `forex_bot/entry_capture.py` `db54cb4073f831cd12e76fcb6fe4e654c50a70704a208cb454ad59a1ec0e2edc`
- `forex_bot/bot_loop.py` `fcf7fa240dcd6b2883d49884eeef6c97dfc98857851572d5d088dbf5207d5aa5`
- `forex_bot/oanda_exec.py` `c8497f3d710c4e272e6ffb2e568429500a157c58fdfdb9b3ca21165c9e63f018`
- `forex_bot/positions.py` `ac33eca30201f283369196f06e97ed34da343225a011348505f6e379fc71099c`
- `forex_bot/trading.py` `b64d58870b2b4d92e16fb763a694a3e19a3ed17251bb8e435d5ec368871d30fd`
- `forex_bot/broker_close_evidence.py` `0e2f545abab1f43f879111efd643439bfcb2a7cc7ff8431e36925b5c144626cf`
- `forex_bot/broker_exit.py` `5f5a329c351cd7856dc7268be2707db99b1b84419a0d60e1d7e7eec42f5ef43f`
- `forex_bot/broker_protection.py` `e57f63ec5d5e4960d4130bd6247253e8d0220502e7f84328ce38f667c97bc768`
- `forex_bot/live_manage.py` `b17c6cc370ea186d9deac1fdfba2d57dd5e26ea71d2be6ed0b2afa64302e9d71`
- `forex_bot/profit_protection.py` `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`
- `forex_bot/execution.py` `6602e363171e3aac4bc4b597ddb805c454c7ca40f7d1fe3fddf542f6a1ab86e2`
- `forex_bot/reconciliation.py` `852a6e2a4da35bce50e68f82cd2e625f25bf36a707a3ad258c3c9d09011a9dbd`
- `main.py` `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb`

Gate hashes still match:

- `data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py` `75a2031a5dd199996eec0b533cf4a83b44362d366fad65ff3585b8151bc18cac`
- `data/research/adaptive_ensemble/r59/live_session_gate.py` `2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2`
- `data/research/adaptive_ensemble/r60/live_session_gate.py` same as R.59
- `data/research/adaptive_ensemble/r61/live_session_gate.py` `2f89959f8cae0e45589b16d159f038af370aa9cec592455784046ef57230c4c0`

`REAL_SESSION_SOURCE_ENABLEMENT = False` remains in the phase-6 gate. The marker hash above was rechecked after the edits. No permit file was created.

`forex_bot/bot_loop.py` was not edited. `run_startup_and_one_iteration` still calls `execute_startup_sequence` and then `_execute_bot_cycle`. `live_management_permitted()` remains the management gate inside that cycle. The fencing check was added inside `live_management_permitted`, so the cycle source did not need to change.
