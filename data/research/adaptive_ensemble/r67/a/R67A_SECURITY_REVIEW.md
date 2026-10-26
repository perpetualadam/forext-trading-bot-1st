# R.67A Security review

Design-only stage. Markdown under `data/research/adaptive_ensemble/r67/a/` is the only write. Operational Python, R.56–R.66 reports, configuration, and git history were not modified.

## Isolation

| Check | Result |
| --- | --- |
| Operational Python edited | No |
| `main.py`, `forex_bot.app`, `run_bot` executed | No |
| `forex_bot` imported | No. `forex_bot.config` calls `load_dotenv()` |
| `.env`, secrets, credentials, account payloads | Not opened |
| OANDA, including the practice host | Not contacted. `REAL_NETWORK_EXECUTION_NOT_TESTED` |
| Orders placed, amended, or closed | No |
| Source gate or activation permit | Unchanged. Permit file remains absent |
| R.62–R.65 integrated | No |
| Working tree cleaned or reset | No |
| Strategy, sizing, stop distances, trading parameters | Unchanged. `PROTECTION_FRESHNESS` is an unnamed symbol, not a new setting |

The local `oandapyV20` package was read and imported to inspect `PositionCloseRequest`, `PositionClose`, `OpenPositions`, `TradeDetails`, and `TradeClose`. That import does not load the bot and does not take a token. No `client.request` ran.

## Source boundary

Commit `d080d897945bc44fa37c02caab504ed707146bec`.

These hashes match the R.66 security review, so the design is not applied to a drifted tree:

| Path | SHA-256 |
| --- | --- |
| `forex_bot/bot_loop.py` | `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` |
| `forex_bot/live_manage.py` | `60d87b8665620743467832758032857e975d32da15322307a0c331009cc7b25d` |
| `forex_bot/reconciliation.py` | `295686792ab017cfc8dfba8fd0add6b2b66a3008304ade141e899af7e86e776b` |
| `forex_bot/oanda_exec.py` | `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8` |
| `forex_bot/positions.py` | `e63ac07e6677ae5707a2a75888bcd5c39df5957ab34547659546e8546d537f2a` |
| `forex_bot/execution.py` | `6602e363171e3aac4bc4b597ddb805c454c7ca40f7d1fe3fddf542f6a1ab86e2` |
| `forex_bot/trading.py` | `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7` |
| `forex_bot/app.py` | `1883d3c94a570b66782b7079bcd64d7657c83c0cd6faa385cab7a65bc2d56bd1` |

`REAL_SESSION_SOURCE_ENABLEMENT = False` remains in the R.56, R.59, R.60, and R.61 gate copies from the R.66 check. This stage did not reopen those files for editing. Consumed marker from R.66: size 10, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`. It was not rewritten.

The production entry refusal is part of the contract: observation of a broker position is not permission to open another one.

## Authority this design refuses

- Import, `execution_kind`, a trade id, `broker_order`, and execution mode do not grant management or a close.
- A local stop price does not grant a claim of broker protection and does not authorise a new stop order.
- A RAM delete does not grant a claim that the broker position is flat.
- An unresolved close does not grant a second close.
- Restart does not grant execution authority.
- The bot must not block a human using the broker's own controls. No account-lock call is added.

## Unverified broker facts

Hedging permission on the account, live OpenPositions and TradeDetails payloads, `PositionClose` partial-fill allocation across trades, and whether close client extensions are echoed are `NOT_VERIFIED`. The contract uses only the distinctions present in the bot parser and the installed client types.

Production trading remains NO-GO.
