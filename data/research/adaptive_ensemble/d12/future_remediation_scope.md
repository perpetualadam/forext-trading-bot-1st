# Future remediation scope

Do not edit these files in D.12. The smallest later change is in `forex_bot/app.py`.

At the stop call, capture the string. If it is `STOP_INCOMPLETE_WORKER_ALIVE`, log it and append that status to the cleanup-error list. Continue task cleanup. Do not raise, because a normal long poll can outlive the 2 second join and a raise would fail an otherwise successful shutdown. Do not join forever. Do not release the database while the worker is alive.

At the start call, remember the stored thread identity. If that same thread is still alive after start, log that this lifespan did not create a worker. Do not fail startup. `start_telegram_control` is already non-fatal, and trading startup does not require Telegram to have started.

Do not change `telegram_control.py` or `database.py` for this reporting gap. Do not clear worker ownership. Do not change live-order authorisation or strategy activation.
