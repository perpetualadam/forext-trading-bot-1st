# Telegram startup interface

`start_telegram_control` at `forex_bot/telegram_control.py` lines 1172–1198 returns `None` on every path that returns to the caller.

`None` covers all of these:

- Commands disabled, at lines 1175–1178. A configured bot logs `Telegram commands disabled (TELEGRAM_COMMANDS=0)`.
- A live stored worker, at lines 1183–1184. The function returns immediately. It does not log, does not clear `_stop_event`, and does not start another thread.
- A newly assigned worker, at lines 1185–1194.
- A start exception swallowed at lines 1195–1198. The log says trading continues.

Public callables are command handlers plus `telegram_configured`, `commands_enabled`, `start_telegram_control`, `stop_telegram_control`, and `reset_telegram_control_for_tests`.

`commands_enabled` reports configuration. It does not report whether a start was refused. There is no public worker-state accessor, start-result object, or health payload that distinguishes a new worker from a refused start.

`app.py` therefore cannot tell `TELEGRAM_STARTED` from `TELEGRAM_START_REFUSED_OLD_WORKER` or `TELEGRAM_DISABLED` through a supported interface. Reading `_poller_thread` or `_stop_event` from `app.py` is outside the supported contract.

Markers: `D13_START_REPORTING_INTERFACE_MISSING` and `D13_SCOPE_EXPANSION_REQUIRED`.

Startup-refusal reporting was not implemented. `telegram_control.py` was not modified.
