# R.80 safety gates

Evidence class: static source inspection after the edit, plus the executed suites.

`REAL_SESSION_SOURCE_ENABLEMENT = False` remains in:

| Gate | SHA-256 |
| --- | --- |
| `r56/phase6_connection_enablement/live_session_gate.py` | `75a2031a5dd199996eec0b533cf4a83b44362d366fad65ff3585b8151bc18cac` |
| `r59/live_session_gate.py` | `2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2` |
| `r60/live_session_gate.py` | `2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2` |
| `r61/live_session_gate.py` | `2f89959f8cae0e45589b16d159f038af370aa9cec592455784046ef57230c4c0` |

Also unchanged: `bot_loop.py` `fcf7fa240dcd6b2883d49884eeef6c97dfc98857851572d5d088dbf5207d5aa5`, `positions.py` `ac33eca30201f283369196f06e97ed34da343225a011348505f6e379fc71099c`, `trading.py` `b64d58870b2b4d92e16fb763a694a3e19a3ed17251bb8e435d5ec368871d30fd`, `live_manage.py` `b17c6cc370ea186d9deac1fdfba2d57dd5e26ea71d2be6ed0b2afa64302e9d71`, `entry_journal.py` `aea5b74e0f431a90b1bd410d650295a5b79d4d901f77391234cd9ddaa5653a07`, `close_journal.py` `4593b42c27b099bc87a225bc7de50b6a9908d41dca5464889f9f26e5d500ef9b`, `broker_close_evidence.py` `0e2f545abab1f43f879111efd643439bfcb2a7cc7ff8431e36925b5c144626cf`, `recovery_owner_lock.py` `6a60e2264f703bbc9192658f0c82e54f3cd65a773b72a0afe916dae4163a9361`, `recovery_repair.py` `bb0e387b7a32475747aa894cf417f61ce6f0b765306181a2a0cda0ab19a818d0`.

The new check calls the existing `live_management_permitted()`. It does not assign `_fencing_epoch`, force `RECOVERY_COMPLETED`, or make `live_management_permitted()` return true. A failed recheck raises `EntryGuardRefusal` or `CloseGuardRefusal`. The already-consumed permit is not released and is not retried.

`R80_SOURCE_GATES_UNCHANGED`: PASS.
`R80_R79_INTEGRATION_PRESERVED`: PASS. Windows and Linux R.79 suites were 17 passed after the edit.
`R80_NO_LIVE_PERMIT`: PASS.
