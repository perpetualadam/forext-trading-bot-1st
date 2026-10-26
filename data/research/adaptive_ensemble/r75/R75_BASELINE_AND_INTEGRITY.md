# R.75 Baseline and Integrity

Recorded before operational edits and re-checked after them.

| Check | Result |
| --- | --- |
| HEAD | `d080d897945bc44fa37c02caab504ed707146bec` |
| Branch | `main` |
| Dirty porcelain count after R.75 | 287, including the pre-existing dirty tree. Not cleaned. |
| Consumed marker SHA-256 | `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` |
| Consumed marker size | 10 bytes. Body not printed. |
| `one_session.permit` files | 0 |
| `REAL_SESSION_SOURCE_ENABLEMENT` | `False` in r56 phase6, r59, r60, and r61 `live_session_gate.py` |

The R.74 expected hashes matched before editing. After R.75, these files still match that table:

| File | SHA-256 |
| --- | --- |
| `forex_bot/bot_loop.py` | `fdc1a83ce0384ea3f3c46980eb8fe252ddec51cea1372ccd2db78ef959ffc897` |
| `forex_bot/broker_exit.py` | `5f5a329c351cd7856dc7268be2707db99b1b84419a0d60e1d7e7eec42f5ef43f` |
| `forex_bot/reconciliation.py` | `852a6e2a4da35bce50e68f82cd2e625f25bf36a707a3ad258c3c9d09011a9dbd` |
| `forex_bot/broker_protection.py` | `e57f63ec5d5e4960d4130bd6247253e8d0220502e7f84328ce38f667c97bc768` |
| `forex_bot/live_manage.py` | `b17c6cc370ea186d9deac1fdfba2d57dd5e26ea71d2be6ed0b2afa64302e9d71` |
| `forex_bot/profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |
| `forex_bot/execution.py` | `6602e363171e3aac4bc4b597ddb805c454c7ca40f7d1fe3fddf542f6a1ab86e2` |
| `main.py` | `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb` |

These files differ because R.75 edited them:

| File | Role of the edit |
| --- | --- |
| `forex_bot/close_journal.py` | Schema 2, `network_permit`, `managed_positions`, permit claim |
| `forex_bot/broker_close_evidence.py` | Guarded path issues a permit and persists the position |
| `forex_bot/positions.py` | Quarantine flag blocks management |
| `forex_bot/oanda_exec.py` | Final `PositionClose` boundary |
| `forex_bot/trading.py` | Live `execute_trade` refuses before HTTP |

Journal schema version is 2. `open_journal` (`close_journal.py` lines 719–741) refuses any other version with `unsupported_schema`. A missing file is `missing_journal`. An integrity failure or empty file is `corrupt_journal`. Bootstrap without `acknowledge_empty` or a preexisting blocker leaves `closes_authorised=0`, and `reserve` raises `bootstrap_does_not_authorise_closes`.

No reset, stash, clean, or commit was performed.
