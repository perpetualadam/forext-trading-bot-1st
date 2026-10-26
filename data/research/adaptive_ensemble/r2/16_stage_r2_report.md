# STAGE R.2 — OFFLINE DECISION-PATH CONFIRMATION AND LOCAL HISTORICAL SESSION INVENTORY REPORT

## 1. Executive summary

- Overall classification: `R2_OFFLINE_READINESS_PARTIAL`
- Gate A: PASS. Protected hashes matched.
- Gate B: PASS. The live decision path was traced from source. It was not run.
- Gate C: PASS. All six names were mapped. None has its own live buy/sell rule.
- Gate D: PASS. A socket and dotenv barrier was installed before the tests.
- Gate E: BLOCKED as a full pass. The safe synchronous tests passed. Four async tests stopped because Windows asyncio tried to open a local self-pipe and the barrier refused it. No order function was reached. Several required behaviours were not covered by any test.
- Gate F: PASS. Local candle files were inventoried.
- Gate G: PASS. The count of 27 was reproduced. The required 40 was not met.
- Gate H: PASS. The readiness answers below are from this run.
- Gate I: PASS. Protected files were unchanged after the run.
- Tests executed: 53
- Tests passed: 49
- Tests failed: 4
- Tests not run on purpose: 2, plus the D.15 application-lifespan tests
- Behaviours not evaluated: E05, E06, E14, E15
- Historical sessions: 27
- Recomputed sessions: 27
- Required sessions: 40
- Additional eligible sessions: 0
- Production source modified: no
- Network requests: 0
- Broker requests: 0
- Recommended next action: a later offline stage for the inactive-entry return and the uncertain-order path. Do not start it now.

## 2. Safety and scope

- Production access: none
- Broker access: none
- Telegram access: none
- Discord access: none
- Network access: none
- DNS lookups: none. `getaddrinfo` was replaced before the tests.
- Socket attempts: 5 blocked constructions. They came from asyncio's local self-pipe, not from OANDA. No operating-system socket was opened.
- Application startup: none
- Trading-loop execution: none. `forex_bot.app` and `bot_loop.py` were not imported.
- Strategy activation: the test process ended with all six flags false. One test turns `scalp` on and then off inside the R.2 safety file. That file is under `r2/tmp`.
- Live-order authorisation: left blocked. The two tests that would set it to ALLOWED were not run.
- Package installation: none
- Docker / WSL / VM: none
- Git changes: none. HEAD stayed `d080d897945bc44fa37c02caab504ed707146bec` on `main`.

## 3. Baseline

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working tree: already dirty. The same five application files and the Dockerfile show as modified against the commit. They were not edited by this stage.
- Protected hashes: all ten matched both before and after. See `02_git_and_baseline.json` and `15_final_integrity.json`.
- Additional source hashes were recorded before the tests and matched afterwards.
- Earlier G.4, G.5, and D.15 files were read and not rewritten.

## 4. Actual live decision path

The bot does not pick a strategy and then let that strategy decide buy or sell.

It loads candles, manages any position it already has, and refuses a new trade while live-order permission is blocked. It then picks one of the six names. If that name is off, it stops before it calculates a size and before it can send an order. If the name is on, buy or sell still comes from a shared vote: the fast average versus the slow average, plus a small momentum check, unless optional external voters are configured. Reinforcement learning can say no. It cannot change the side. The stop, target, and size are shared by every name.

The shadow rules in `forex_bot/shadow/signals.py` are a separate offline copy. The live loop does not call them.

`STRATEGY_NAME_DOES_NOT_SET_SIDE` is a written note in `forex_bot/decision_quality/live_path.py`. Nothing in the running path reads that note. The running path agrees with it anyway, because the side is taken from `ai.vote`.

Two source risks are not covered by today's tests. A blank direction is forced to BUY. A timeout is classified as uncertain and then marked as a failed reservation, so a later cycle can create a new order id.

Details and line numbers are in `03_decision_path_trace.md`.

## 5. Six-strategy mapping

| Name | Live buy/sell rule of its own | Shadow rule | Active by default | Own stop and size |
|---|---|---|---|---|
| scalp | No | Momentum against the averages | No | No |
| trend | No | Averages aligned and price on that side | No | No |
| mean_reversion | No | Outside the Bollinger bands | No | No |
| swing_trend | No | Same shadow rule as trend | No | No |
| swing_mean_reversion | No | Same shadow rule as mean reversion | No | No |
| swing_breakout | No | Beyond the prior high or low | No | No |

While a name is inactive, the source returns before sizing. That return was not executed today. The default-off flag was executed and passed.

## 6. Offline test preflight

- Selected: the activation-default file, the D.15 hash-comparison file, and the execution-safety tests that do not grant live permission.
- Excluded: the two tests that set authorisation to ALLOWED, and every D.15 test that imports the application and starts its lifespan.
- Network barrier: socket construction and name lookup raise before a connection.
- Credential barrier: `load_dotenv` was replaced and did not open a file. It was called once.
- Database isolation: order persistence was off, so the duplicate-id test stayed in memory.
- Output isolation: pytest temp files and the safety file stayed under `r2`.
- Preflight verdict: PASS.

## 7. Safety test results

| ID | Result | What happened |
|---|---|---|
| E01 | PASS | All six default to inactive. |
| E02 | PASS | The string `"true"` does not activate. |
| E03 | PASS | The number 1 does not activate. |
| E04 | PASS | Only boolean True activates. |
| E05 | NOT_EVALUATED | No test ran the return that happens before sizing. |
| E06 | NOT_EVALUATED | No test ran the return that happens before an order. |
| E07 | PASS | Authorisation stays blocked. |
| E08 | PASS | A missing safety record fails closed. |
| E09 | PASS | An invalid safety record fails closed. |
| E10 | PASS | Loading a safety file does not turn a saved ALLOWED into live permission. The app itself was not restarted. |
| E11 | PASS for the synchronous checks | Paper kinds are refused before a broker call. The async versions did not reach that check. |
| E12 | PASS | A live kind stays blocked until authorisation exists. The path that grants authorisation was not run. |
| E13 | PASS | A repeated client id is rejected in memory. |
| E14 | NOT_EVALUATED | No test covered a timeout. The source marks that case as failed. |
| E15 | NOT_EVALUATED | No test compared a shadow rule with the live vote. |
| E16 | PASS | Production files and production state were not changed. |

The four failed tests are `test_async_open_refuses_paper_kinds_before_api` (three cases) and `test_paper_mode_open_never_calls_sync_place`. They failed because `asyncio.run` on Windows creates a local self-pipe. The barrier stopped that pipe. They do not show that a paper order reached OANDA.

Activation run: 38 passed. Execution run: 11 passed, 4 failed, 2 deselected.

## 8. Local data inventory

The G.3 normalised files are the candle set G.4 used. Each has bid and ask columns. Invalid bid/ask rows: 0. Duplicate timestamps: 0. Times are stored in UTC. The span is 2026-09-01 00:00 UTC through 2026-10-09 07:00 UTC.

| File | Rows | SHA-256 |
|---|---|---|
| AUD_USD_M5.csv | 8146 | `d75312decbb4c72858621a0b5a9af6103f72b01593ae26e9df4ef19a06104583` |
| EUR_USD_M5.csv | 8148 | `c9016c8443ecc44fd0cf6ed5acb44656eae09ee3ef5b7d9fe9a334152c764b14` |
| GBP_USD_M5.csv | 8148 | `272c7ff448ff91f587946c8b7a4335bacd04ae488c95f066e4a29cfec700c4f6` |
| USD_CAD_M5.csv | 8147 | `e8fd5cf2acd20c481167d5ef5d0b77b7beaed9c190a8832c1291ffdee4475743` |
| USD_CHF_M5.csv | 8123 | `7119ac28e67faaa24246c2bf9e0b8a863092328fa64b0694b4132e6835ea249f` |
| USD_JPY_M5.csv | 8141 | `542a307964b9a365d28ca923905b5be6595c136261d52e92c154d0d29b35fd42` |

Thirty-six raw G.3 pages were hashed and are not a second session source. Three other research CSV files exist. They are macro or event tables, not this six-pair candle set, so they were not eligible. Production `data/ops` and `v2_shadow` were not opened.

## 9. Session recount

- Original count: 27
- Recomputed count: 27
- Match: yes
- Additional eligible count: 0
- Threshold: 40
- Threshold met: no
- Complete dates: 2026-09-02 through 2026-10-08, excluding weekends, 27 dates
- Rejected: 2026-09-01 and 2026-10-09, both partial boundary sessions, for every pair
- Conversion status: ok
- Unresolved gaps: 0
- Reproducibility: the original G.4 function and the original window were used. No bars were invented. The 40 rule was not lowered.
- Profitability evaluation: not run

## 10. Remaining blockers

Critical safety: the timeout path can clear a reservation and allow a later new order id. A blank direction can be forced to BUY. The inactive return before sizing is not yet executed in a test.

Strategy evidence: six names are not six live rules. 27 sessions remain short of 40. No edge has been measured.

Broker readiness: no practice test is authorised. Spread-bet instrument identity is still unknown. Financing is unmodelled.

Optional infrastructure: Docker work does not answer these questions.

## 11. Next three priorities

1. Execute, offline, the check that an inactive name returns before sizing and before an order. Do not start the app.
2. Execute, offline, a fake timeout and show whether a second order id can be created. Do not contact the broker.
3. Leave the session bar at 40. Do not download data until a separate approval. Do not publish a profit result on 27 sessions.

## 12. Recommended next stage

R.3, only after a new approval: offline fixtures for the inactive return and the uncertain-order path. It is the best next step because those are the safety holes this stage could see but could not execute. More Docker work will not close them. A download will not explain the live decision.

## 13. Final integrity

- Protected source unchanged: yes
- Earlier evidence unchanged: yes
- Datasets unchanged: yes. They were hashed and read.
- Unexpected project files: none outside `data/research/adaptive_ensemble/r2`
- Unexpected processes: none left running
- Prohibited operations: none

## 14. Final classification

`R2_OFFLINE_READINESS_PARTIAL`

The stage stayed inside its safety limits. The decision path, the six-name map, the default-off tests, the authorisation block, and the 27-session recount are real evidence. A full pass is not claimed, because the inactive return, the timeout path, and the async order tests were not completed.

## 15. Hard stop

No production deployment. No live trading. No practice-account orders. No rollback. No subsequent stage without fresh approval.

PRODUCTION DEPLOYMENT: NO-GO.  
LIVE TRADING: NOT AUTHORISED.  
PRACTICE-ACCOUNT ORDERS: NOT AUTHORISED.  
ROLLBACK: NO-GO.
