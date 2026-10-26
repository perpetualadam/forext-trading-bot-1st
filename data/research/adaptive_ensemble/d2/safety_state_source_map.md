# Safety-state source map

File: `forex_bot/live_safety.py`. There is no separate data class. The document is a dict.

## Constants

- `SCHEMA_VERSION = 1` at line 19. Supported version is 1 only.
- `AUTH_BLOCKED` / `AUTH_ALLOWED` at lines 20-21.
- Reasons at lines 22-30, including `REASON_FUTURE_SCHEMA` and `REASON_UNREADABLE` added in this stage.
- `KNOWN_STRATEGY_NAMES` at line 31: scalp, trend, mean_reversion, swing_trend, swing_mean_reversion, swing_breakout.

## Representation

- Authorisation is `live_order_authorisation.state` with `reason`, `updated_at_utc`, and `source`.
- Each known strategy row uses `active` as a JSON boolean, plus `authorised_for_live`, `disable_reason`, `changed_at_utc`, `sample_count`, `sharpe`, and `loaded_from_durable`.
- Default document: `_blank_document` at line 127. It is BLOCKED and every known strategy is inactive.

## Read, write, and recovery

- `_version_kind` line 144 separates a future integer version from an invalid type.
- `_validate_document` line 157 accepts only version 1, a BLOCKED or ALLOWED state, and a boolean `active` on every known row.
- `_inspect_durable` line 190 classifies missing, valid, future, invalid, and unreadable without writing.
- `_atomic_write` line 225 renders JSON, writes a same-directory temporary file, flushes, fsyncs, then `os.replace`.
- `_document_for_update` line 251 returns a missing-file blank or a valid document, and raises `SafetyStateProtected` otherwise.
- `_preserve_unknown` line 261 copies keys that are not in the known set.
- `initialise_fail_closed` line 383 is the startup entry. It writes only for a missing file or a valid version-1 document.
- `_refuse_existing` line 365 is the non-destructive fail-closed path.
- `persist_evolve_disable` line 427, `operator_set_live_order_authorisation` line 461, and `operator_set_strategy_active` line 497 are the other writers. They use `_document_for_update`.

## Callers, not modified

- Startup: `forex_bot/app.py` lifespan calls `initialise_fail_closed`.
- Scheduler: `forex_bot/bot_loop.py` calls `persist_evolve_disable` and reads `live_order_auth_state` / `live_safety_initialised`.
- Order gate: `forex_bot/execution.py` and `forex_bot/oanda_exec.py` call `live_open_blocked_reason` and `assert_new_live_exposure_allowed`.
- `forex_bot/live_safety_preflight.py` reads `_validate_document` and creates a file only when the path is absent.

The public signatures of the startup, scheduler, and order-gate functions were not changed. The defect is contained in this module.
