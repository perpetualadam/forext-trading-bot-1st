# Telegram start contract

`start_telegram_control` returns `None`. It does not raise to the caller. If a stored worker is alive, it returns at lines 1183-1184 without a log and without clearing the stop event.

`app.py` line 370 calls it and ignores the result. Startup has already passed the safety preflight by then. A refused start is not a startup failure.

The source comment on a start exception says trading continues. Telegram startup is optional for the trading lifespan, not a required success signal.
