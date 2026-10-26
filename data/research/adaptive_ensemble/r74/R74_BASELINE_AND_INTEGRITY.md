# R.74 Baseline and Integrity

Recorded before any R.74 edit.

- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Short status lines: 282
- Working tree was not reset, stashed, cleaned, or committed.

Expected R.73 hashes all matched:

| File | SHA-256 |
| --- | --- |
| `forex_bot/broker_close_evidence.py` | `7282c32473bb25d76475a3e1d2c74f1fa0a35165fc72469108a3109784062315` |
| `forex_bot/bot_loop.py` | `f92ab293cd64eeeaca15fb202432e4ef8ba6cf25723f18c28c8e293d1347990d` |
| `forex_bot/positions.py` | `0f5259b1357212b51f81640668cc430dba5c2e9909f173770932543ba5759e54` |
| `forex_bot/reconciliation.py` | `852a6e2a4da35bce50e68f82cd2e625f25bf36a707a3ad258c3c9d09011a9dbd` |
| `forex_bot/broker_exit.py` | `018d2cdd0658d17a15cb5dadb44f9ca259dc026a7739e2134d87886ec3a64a9f` |
| `forex_bot/oanda_exec.py` | `ebb1fbcffc5beb91e28c95bc2024eeed22e0349c21d737c837d606118dc042cb` |
| `forex_bot/broker_protection.py` | `e57f63ec5d5e4960d4130bd6247253e8d0220502e7f84328ce38f667c97bc768` |
| `forex_bot/live_manage.py` | `b17c6cc370ea186d9deac1fdfba2d57dd5e26ea71d2be6ed0b2afa64302e9d71` |
| `forex_bot/profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |
| `forex_bot/trading.py` | `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7` |
| `main.py` | `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb` |

Consumed marker size 10, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`. Permit files found: 0.

`REAL_SESSION_SOURCE_ENABLEMENT = False` in:

- `data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py`
- `data/research/adaptive_ensemble/r59/live_session_gate.py`
- `data/research/adaptive_ensemble/r60/live_session_gate.py`
- `data/research/adaptive_ensemble/r61/live_session_gate.py`

`forex_bot/profit_protection.py`, `forex_bot/trading.py`, `forex_bot/broker_protection.py`, `forex_bot/live_manage.py`, `forex_bot/oanda_exec.py`, `forex_bot/reconciliation.py`, and `main.py` were not edited in R.74.

No `.env` was loaded. `main.py` was not started. PostgreSQL was not contacted. OANDA was not contacted.
