# R.66 Security review

This stage wrote Markdown under `data/research/adaptive_ensemble/r66/` only. It did not modify operational source, configuration, strategies, database schema, R.56–R.65, or git state.

## Isolation

| Check | Result |
| --- | --- |
| `main.py`, `forex_bot.app`, and `run_bot` executed | No |
| `forex_bot` imported | No. `forex_bot.config` calls `load_dotenv()` at import, so the audit hashed and parsed files as text |
| `.env` opened | No |
| OANDA HTTP | No. `REAL_NETWORK_EXECUTION_NOT_TESTED` |
| Orders | No |
| Activation permit created | No. `one_session.permit` was absent |
| Source gate enabled | No |
| Database migration | No |
| Formatter or linter that rewrites source | No |
| Experimental lifecycle manager integrated | No |

The only code execution was a standard-library hasher and an `ast` parse of `bot_loop.py`. It did not import the package.

## Gates and permit

`data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py` contains `REAL_SESSION_SOURCE_ENABLEMENT = False`.

Consumed marker `data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_activation/one_session.consumed`: size 10, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`. The body was not printed.

`one_session.permit` in that directory: absent.

R.64 archive: 7642 bytes, SHA-256 `c80ce9dc784d5d152fd2d78bfb855d702babe6d90e6473439c0b6725af1af0b5`.

R.65 archive: 4917 bytes, SHA-256 `084f5e4f4104e8fcfb687d713acc04c5ea2aa0587faffa6a93d3f96e526606ae`.

Effective live-order authorisation in `live_safety.initialise_fail_closed` is set blocked on process start. This audit did not call that function.

## Repository identity

Commit: `d080d897945bc44fa37c02caab504ed707146bec`.

The working tree was already dirty before R.66, including modifications to `forex_bot/app.py`, `bot_loop.py`, `oanda_client.py`, and other operational files, plus a large set of untracked research directories. Those edits were not made by this stage. This audit describes the working tree that was present, not a clean `HEAD`.

Hashes below were taken before the reports were written. The post-audit command recomputes the same operational hashes and must match.

| SHA-256 | Bytes | Path |
| --- | --- | --- |
| `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb` | 585 | `main.py` |
| `1883d3c94a570b66782b7079bcd64d7657c83c0cd6faa385cab7a65bc2d56bd1` | 33204 | `forex_bot/app.py` |
| `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` | 168595 | `forex_bot/bot_loop.py` |
| `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7` | 19115 | `forex_bot/trading.py` |
| `6602e363171e3aac4bc4b597ddb805c454c7ca40f7d1fe3fddf542f6a1ab86e2` | 8653 | `forex_bot/execution.py` |
| `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8` | 24707 | `forex_bot/oanda_exec.py` |
| `e08b6df42bc9954e6558d48643fdaf3b66b92b1d255561909eb0100618826923` | 19656 | `forex_bot/oanda_client.py` |
| `e4310d1cd694c3f2a8791b308666fa15ae6ba1a82bdc67a99c5788ffe70ad546` | 21695 | `forex_bot/live_safety.py` |
| `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` | 24418 | `forex_bot/profit_protection.py` |
| `b45b2f7e7f684686eddd2ddf9f2d6d1c3919678ec128c38665f38c99c3ab3222` | 6613 | `forex_bot/strategy_meta.py` |
| `6c9469e0e6417828dee5a41f17ff84345635e73940f13b46f05b9251385c5e7a` | 8856 | `forex_bot/ai_ensemble.py` |
| `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e` | 2243 | `forex_bot/rl_agent.py` |
| `64fe62a7e5fd997b7ea3ecc69b0bbc09ce5d0bc8ede18180a8bd16b209c52fe9` | 3539 | `forex_bot/indicators.py` |
| `0949a084722697c80cdda5da8c1b7e69ea47dc19c5f718b1f43668a0bb5ae4b4` | 13326 | `forex_bot/portfolio_exposure.py` |
| `5911c79a8f10fb7bf41df275d3e9970118d48c30ec763e8f486475c8e7dbf8f1` | 14082 | `forex_bot/execution_risk.py` |
| `295686792ab017cfc8dfba8fd0add6b2b66a3008304ade141e899af7e86e776b` | 32632 | `forex_bot/reconciliation.py` |
| `827ff6675bff7e205e0165911ab9ea74eb7104caa14c19628d1d6509877a9a0a` | 13508 | `forex_bot/orders.py` |
| `e63ac07e6677ae5707a2a75888bcd5c39df5957ab34547659546e8546d537f2a` | 7212 | `forex_bot/positions.py` |
| `2de81213403d2092fab201a4704bb10ae85bdc861c9c854bac6e385e406e204c` | 19811 | `forex_bot/entry_geometry.py` |
| `60d87b8665620743467832758032857e975d32da15322307a0c331009cc7b25d` | 5066 | `forex_bot/live_manage.py` |
| `13db72c668f60a8a50bf148789070c29cb941be748a51b298bd7bcb2971f99fd` | 2421 | `forex_bot/config.py` |

`main.py` still matches the historical pin `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb`. Other operational files in this table are the dirty working tree. They were not rewritten by R.66.

## Credential and broker boundary

No token, account id, or practice host was printed. Order helpers that would send `OrderCreate` or `PositionClose` were read and not called. Research gates under R.59, R.60, and R.61 were not edited. A text search of those three `live_session_gate.py` copies is part of the post-audit integrity command.

## Offline checks

No pytest module was run. Importing `forex_bot` loads `.env` from `forex_bot/config.py`, and many repository tests import the application. Those suites were left unrun rather than treated as passes.

| Command | Purpose | Platform | Result | New or existing | What it exercised |
| --- | --- | --- | --- | --- | --- |
| `python -B` standard-library `ast.parse` of `forex_bot/bot_loop.py` | Confirm `continue_existing_production_broker` is never assigned | Windows 11 | No assignment nodes. The string occurs once | One-off inspection, not a repository test | Source text only. Not production logic at runtime |
| `python -B` SHA-256 of the operational paths listed above, before and after the reports | Prove R.66 did not edit them | Windows | `HASH_MISMATCHES 0` | One-off inspection | File bytes |
| Text search of R.56, R.59, R.60, and R.61 `live_session_gate.py` | Source gate still false | Windows | Each file contains `REAL_SESSION_SOURCE_ENABLEMENT = False` | One-off inspection | Source text |

Linux was not used. Behavioural equivalence is `NOT_VERIFIED`.

## Post-audit integrity

Commit remained `d080d897945bc44fa37c02caab504ed707146bec`. The twenty-one operational hashes above matched after the reports were written. The consumed marker, absent permit, R.64 archive, and R.65 archive matched the values in this file. `git status` shows `data/research/adaptive_ensemble/r66/` as the new untracked path from this stage. Other dirty and untracked operational paths were already present and were not edited.

## Residual risk

The application, if started, would build an API client, fetch candles and account data, and reconcile. That is operational behaviour of the source. It was not invoked. Starting it remains out of scope. Production trading remains NO-GO.
