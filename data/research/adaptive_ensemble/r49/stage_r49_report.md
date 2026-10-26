# STAGE R.49 — SECURE OANDA API CREDENTIAL HANDOFF AND CONNECTION PREPARATION REPORT

Classification: `R49_SECURE_OANDA_HANDOFF_PREPARED`

The isolated handoff exists, the synthetic tests pass, and the manual procedure is written. No credential was accessed and no authenticated request was sent. The token is not claimed to be read-only. Prepared does not mean connected or account-verified.

## Branch and preservation

Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`. Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The working tree was already dirty and those unrelated changes were left in place. R.24–R.48 evidence is present. All six strategies are inactive. The quant stub source still returns `quant_stub_removed`. RL on an unseen state is `UNAVAILABLE`. Research lifecycle code stays disconnected. Operational hashes are unchanged. `forex_bot.config` and `forex_bot.oanda_client` were not imported.

## Credentials and network

No real token was read. No real account identifier was read. `.env` was not opened. The environment was not searched for secrets. No OANDA request was sent. `NETWORK_EXECUTION` is false.

## Standalone runner

`data/research/adaptive_ensemble/r49/handoff_runner.py` loads the R.48 gate by path. It does not import the production package and it contains no HTTP client. Started with no arguments, it prints that the network gate is closed and does not prompt. Any command-line argument is rejected, so a token cannot be passed on the command line. The confirmation phrase `APPROVE PHASE B` still raises `R49_NETWORK_GATE_CLOSED`.

A future entry has to be typed in a window opened from the Windows Start menu, not in Cursor's terminal. Hidden typing does not keep a secret out of Cursor, a recorder, or process memory. The current program does not ask for that entry.

## Broker read-only permission

`UNKNOWN`. Local source does not show a broker setting that limits this account's token to GET. A GET-only program would not make the token read-only. The token may be able to trade.

## Synthetic tests

Attempt 1: 2 failed, 4 passed. The source scan hit the key name `requests`, and an empty-string check was true of every error sentence. Attempt 2: 6 passed. The scan still forbids that library name. Empty input is still rejected. No safety check was removed.

## Remaining risks

The account fields are still `NOT_RETRIEVED`. The ticket pip line of £0.00 is still not zero risk. The USD path, the 1.35 fallback, and the missing unit clamp are unchanged. A future connection can still leak a secret if it is typed in Cursor or if the token is written into a file.

## Future user actions

Do not perform them now. After a separate approval of `08_manual_procedure.md`: open Windows Terminal from the Start menu, run only the isolated runner, type the account identifier and token when that later build asks, check that the saved file has no account identifier, and close the window before answering if anything looks wrong. If the window is not trustworthy, do not type the token.

## Recommended next stage

Do not start it from this report. The next approval is the Phase B connection itself, using this procedure, still with no orders and no candle download. It is not a trading stage.

PRODUCTION DEPLOYMENT: NO-GO

PRACTICE ORDERS: NOT AUTHORISED

LIVE TRADING: NOT AUTHORISED

ROLLBACK: NO-GO
