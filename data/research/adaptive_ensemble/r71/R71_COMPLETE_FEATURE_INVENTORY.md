# R.71 Complete Feature Inventory

Primary classifications are in `R71_MASTER_FEATURE_MATRIX.csv`. This page is the narrative index. A function's presence is not reachability. Reachability is not a runtime test. A runtime test is not a broker test.

## Implemented and operationally reachable (14)

F01 entry refusal, F02 ownership, F03 observation import, F04 snapshot completeness, F05 67 percent activation, F06 ATR giveback, F07 4-pip fallback, F08 ratchet, F10 local protection close, F17 paper candle SL/TP, F22 weekend flatten, F26 six-pair list, F30 RL update after a local close, F33 reconciliation.

F05–F08 and F10 run only after `position_management_permitted` returns true (`bot_loop.py` 795–802, then 854). An observation returns before profit protection.

## Implemented but blocked (9)

F11 live `PositionClose`, F13 fixed-pip SL/TP call site, F14 ATR stop option, F15 `stopLossOnFill`, F23 sizing call site, F25 portfolio cap call site, F27 strategy selection, F28 AI ensemble entry use, F29 RL entry gate.

The block is `dispatch_production_iteration` at `bot_loop.py` 1135–1148. Continuation requires status `continue_existing_production_broker`. `evaluate_one_instrument_iteration` returns `blocked` and does not assign that status (3336–3342).

## Partially implemented (3)

F16 `broker_sl_tp_hit` is called and always returns false. F24 sizing converts USD-base pairs by dividing by mid and leaves other pairs in quote currency. F34 database helpers exist and were not connected to a database in this audit.

## Research-only (4)

F31 adaptive-ensemble research, F32 shadow engine, F35 containment supervisors, F40 research source gates. The gates stay false. They do not wrap `main.py`.

## Design-only (2)

F36 close-operation state machine. F37 broker-protection evidence contract.

## Missing (7)

F09 durable MFE, F12 broker trailing stop, F18 breakeven, F19 strategy partial close, F20 close filled-unit confirmation, F21 close idempotency, F38 restart recovery of positions.

## Not verified (1)

F39 profitability. No performance figure is stated.
