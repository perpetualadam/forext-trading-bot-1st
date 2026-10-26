# Source change log

## Modified

- `forex_bot/bot_loop.py`
  - Pre `e63696df64b5f8591eabec4747f1d05d486906342a6841f2c1d1e8266f6083c5`
  - Post `2585b550085e47b84dd0d353b207709797d28abca28b7bb1ee4d3e956c0c8732`
  - Added `dispatch_production_iteration`.
  - `evaluate` delegates to it when dependencies are supplied.
  - `_evaluate_impl` calls it for a new entry and returns unless the continuation sentinel is present. The sentinel is not produced.
- `forex_bot/database.py`
  - Pre `16363fdc26929ed0a6fe71837806ba96c51043df76fa3d524a2d26f80736c486`
  - Post `53e1e81827d6456743a1154d1636c05e6acbcfb340dae438912900c46c2d0ff4`
  - `confirm_exposure_flat` no longer releases on a caller-supplied token.

## Assertion and pin updates

- `tests/test_r9_position_safety.py` now expects the flat token to leave the hold in place.
- Hash pins in `tests/test_r8_reservation_safety.py`, `tests/test_r10_offline_startup.py`, and `tests/test_r11_historical_recovery.py`.

## New

- `tests/test_r13_loop_wiring.py`
- `data/research/adaptive_ensemble/r13/`

## Unchanged

`app.py`, `orders.py`, `oanda_exec.py`, `live_safety.py`, `strategy_meta.py`, `telegram_control.py`, `main.py`, requirements, and Docker files.
