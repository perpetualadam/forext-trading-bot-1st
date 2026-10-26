# Source change log

## Modified

- `forex_bot/bot_loop.py`
  - Pre-stage hash `9fbb8c326c35d312b86b88a3d49f395993c2e1fee303afb15a56d7c14c4b2941`
  - Post-stage hash `e63696df64b5f8591eabec4747f1d05d486906342a6841f2c1d1e8266f6083c5`
  - Broker client imports moved into the production functions that use them.
  - Added `evaluate_one_instrument_iteration`.
  - `run_bot` and `_evaluate_impl` were not replaced and were not called.

## Hash pins only

- `tests/test_r8_reservation_safety.py`
- `tests/test_r10_offline_startup.py`
- `tests/test_r11_historical_recovery.py`

The pins now expect the new `bot_loop.py` hash. The reservation, exposure, and recovery assertions were not weakened.

## New

- `tests/r12_fakes.py`
- `tests/test_r12_single_iteration.py`
- `data/research/adaptive_ensemble/r12/` artifacts and the offline runner

## Unchanged

`app.py`, `database.py`, `orders.py`, `oanda_exec.py`, `live_safety.py`, `strategy_meta.py`, `telegram_control.py`, `main.py`, requirements, and Docker files.
