# R.67C Security review

Design validation only. Executable code is confined to `data/research/adaptive_ensemble/r67/c/poc/`. Reports are under `data/research/adaptive_ensemble/r67/c/`.

## Isolation

| Check | Result |
| --- | --- |
| Operational Python edited | No. Hashes below match the R.67B baseline. |
| `main.py`, `forex_bot.app`, `run_bot` executed | No |
| `forex_bot` imported | No. The test asserts it is absent from `sys.modules`. |
| `.env`, secrets, credentials, account payloads | Not opened |
| OANDA live or practice | Not contacted. `REAL_NETWORK_EXECUTION_NOT_TESTED` |
| Orders placed, amended, or cancelled | No |
| Database schema or migration | No. No PostgreSQL connection. `POSTGRESQL_INTEGRATION_NOT_TESTED` |
| Source gates | Left false. R.56, R.59, R.60, and R.61 `live_session_gate.py` still contain `REAL_SESSION_SOURCE_ENABLEMENT = False`. This stage did not assign them. |
| Activation permit | `one_session.permit` is absent. Consumed marker size 10, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`. Not rewritten. |
| R.62–R.65 integrated | No |
| R.67A and R.67B edited | No |
| Working tree cleaned, reset, or branch-switched | No |
| Strategy, sizing, stops, trading parameters | Unchanged |

## Source boundary

Commit `d080d897945bc44fa37c02caab504ed707146bec`. The working tree was already dirty (269 `git status --short` lines at the start of this stage, including modified operational files and untracked research trees). Those edits were preserved. R.67C added only files under `data/research/adaptive_ensemble/r67/c/`.

| Path | SHA-256 | Against R.67B |
| --- | --- | --- |
| `main.py` | `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb` | MATCH |
| `forex_bot/bot_loop.py` | `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` | MATCH |
| `forex_bot/live_manage.py` | `60d87b8665620743467832758032857e975d32da15322307a0c331009cc7b25d` | MATCH |
| `forex_bot/reconciliation.py` | `295686792ab017cfc8dfba8fd0add6b2b66a3008304ade141e899af7e86e776b` | MATCH |
| `forex_bot/oanda_exec.py` | `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8` | MATCH |
| `forex_bot/positions.py` | `e63ac07e6677ae5707a2a75888bcd5c39df5957ab34547659546e8546d537f2a` | MATCH |
| `forex_bot/execution.py` | `6602e363171e3aac4bc4b597ddb805c454c7ca40f7d1fe3fddf542f6a1ab86e2` | MATCH |
| `forex_bot/trading.py` | `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7` | MATCH |
| `forex_bot/app.py` | `1883d3c94a570b66782b7079bcd64d7657c83c0cd6faa385cab7a65bc2d56bd1` | MATCH |
| `forex_bot/broker_exit.py` | `d9920eed6160c5f26e1db7ee34095488b3457755e5dbf21cffbeda08eb798c12` | MATCH |
| `forex_bot/database.py` | `be83fc2a485af0f392203562a8286082587b0824f235557b6036e69f661f840d` | MATCH |

R.67A and R.67B document hashes were recorded at the start of the stage and those files were not written again:

| Document | SHA-256 |
| --- | --- |
| `R67A_POSITION_OWNERSHIP_CONTRACT.md` | `827bc93043b3510557111d50a91b883069bdda165dfabf63bae8f9b5ea82ec7f` |
| `R67A_AUTHORITY_MODEL.md` | `2cd9010271e780eb3f1010e56863ef9d78a3249fae542461dc2ce5931926868f` |
| `R67A_PROTECTION_STATUS_CONTRACT.md` | `739d26b901aa8e9bd0acc3daaa8f2fc50f025f964fdd7b58e22b79dbc84489f6` |
| `R67A_SOURCE_MAPPING.md` | `38bee8357b997a588fa05c6137f06a07abbaf672dd0d0276b426b386ef2d86ba` |
| `R67A_SECURITY_REVIEW.md` | `a7469d2cac07a80d6384eb51052bcaddd5c8aa82458f5a5e6a8a72a36bde8d3e` |
| `R67B_RECONCILIATION_STATE_MACHINE.md` | `2978b95102ba8901c64b1adb1513f8fb8acbc0af47d703ebd5eaf56708cc529a` |
| `R67B_CLOSE_LIFECYCLE.md` | `0b4021e12cae538ea24a174392be82b7251951458d90bb32607afbb5efd88cf3` |
| `R67B_CONCURRENCY_AND_PERSISTENCE.md` | `ae4de6564e5d130ffcb359a38d843cc4fffcc83e82aa88ad10dbcce1034dcd4e` |
| `R67B_FAILURE_MODE_ANALYSIS.md` | `18fd7d392e6a862b6a9f739e95d5f9027fffd9e0d983d484aa2f1e869d3266da` |
| `R67B_SECURITY_REVIEW.md` | `378ece174a25ae555a322f20e5004ad7941053950bfeba237f5caf37eeb2dc37` |

## What the tests do not prove

The reference model refuses duplicate closes, keeps residual units, and separates exposure from attribution inside its own ledger. The operational reconcile/import path and `PositionClose` sender were not changed and still behave as R.66 described.

## Source archive

`R67C_SOURCE_REVIEW.zip` contains only the reference model and its tests.

| Item | Size in bytes | SHA-256 |
| --- | --- | --- |
| Archive | 13275 | `43aa270bf3e33cd321d6c62f5a1976bbab4c4e667f3b04eef100db46dc9c8bf5` |
| `reference_model.py` | 43721 | `62dca2f7fa218ca01d1f52fc20a5c23baf6b7c2b2ca97cbfe7410dd3816dedab` |
| `test_r67c_contract.py` | 36825 | `b8edb4d12405545587116882b5609f02830500d6395079614f4f2577daa43935` |

The test command is the Windows `python -B -m unittest discover` line in `R67C_TEST_REPORT.md`.

Production trading remains NO-GO.
