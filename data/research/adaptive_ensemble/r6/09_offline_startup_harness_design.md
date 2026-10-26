# Offline startup harness design

Not built and not run.

A later approved harness would need to replace these before importing the app:

| Dependency | Class |
| --- | --- |
| OANDA client and order calls | SAFE_TO_FAKE only after the import path cannot open a socket |
| Account summary | SAFE_TO_FAKE |
| Market candles | SAFE_TO_FAKE |
| PostgreSQL | REQUIRES_DATABASE_ENGINE or a fake that replaces `get_connection` before import |
| Telegram | SAFE_TO_FAKE or skip the task |
| dotenv / .env | SAFE_TO_FAKE. Do not read the real file |
| Live permission | Must stay BLOCKED |
| Strategies | Must stay inactive |
| `run_bot` | UNSAFE_TO_EXECUTE_NOW. The harness should stop before the real loop or replace it |
| `uvicorn` / FastAPI server | UNSAFE_TO_EXECUTE_NOW |

`app.py` currently builds the broker client and starts Telegram inside lifespan. A honest offline startup needs a seam there, which means a later edit to `app.py` or an import-time fake installed before `forex_bot.app` loads. That edit is not allowed in R.6.

The harness must show: process reached order recovery, recovery failure blocks new broker entries, live permission is BLOCKED, all six strategies are inactive, and no socket connected.
