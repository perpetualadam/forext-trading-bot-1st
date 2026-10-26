# R.83 safety gates

Executed by `test_01_baseline_gates_and_profit_hash` on Windows and Linux.

All four gate files contain `REAL_SESSION_SOURCE_ENABLEMENT = False`.

| File | SHA-256 |
| --- | --- |
| `r56/phase6_connection_enablement/live_session_gate.py` | `75a2031a5dd199996eec0b533cf4a83b44362d366fad65ff3585b8151bc18cac` |
| `r59/live_session_gate.py` | `2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2` |
| `r60/live_session_gate.py` | `2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2` |
| `r61/live_session_gate.py` | `2f89959f8cae0e45589b16d159f038af370aa9cec592455784046ef57230c4c0` |

`one_session.permit` was absent before the tests and `tearDown` asserts it stays absent. The consumed-marker hash was checked and its body was not printed. No test started `main.py`, `run_bot`, a broker host, PostgreSQL, or a production journal.
