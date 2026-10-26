# R.72 Operational Integration

## Call path

`forex_bot/bot_loop.py` `_evaluate_impl`:

1. `pos = get_position(symbol)` already happened above this branch.
2. Lines 796–802: `position_management_permitted(pos)` is false, so the function returns before quotes, profit protection, evidence, and close.
3. Lines 803–809: if the row is broker-backed, call `record_management_protection_evidence(pos)`. An exception is logged and does not change the later decision.
4. Existing quote, profit-protection, weekend, and close logic continues.
5. Line 896: `sl_tp_hit = broker_sl_tp_hit(pos)` for broker-backed rows.

`record_management_protection_evidence` is `forex_bot/broker_protection.py` lines 506–518. It calls `collect_broker_protection_evidence` (lines 425–503) and logs the classification. The log line does not include an account id.

`broker_sl_tp_hit` is `forex_bot/live_manage.py` lines 76–82 and returns `False`. The evidence object is not passed into it.

## What the hook does not do

- It does not set `sl_tp_hit`.
- It does not call `execute_trade`, `close_position`, or `close_local_position`.
- It does not write `observation_only`.
- It does not change the entry block. `continue_existing_production_broker` remains a comparison at line 1146. The production status remains blocked at line 3347.

The R.69 suite executed the real `_evaluate_impl` manage path after this edit. One live-shaped run logged `trade_identity_mismatch` from the synthetic trade stub and did not call `execute_trade`. That is the operational function running under the existing synthetic harness, not a mocked parser.

`R72_OPERATIONAL_INTEGRATION_IMPLEMENTED`

`R72_NO_NEW_CLOSE_AUTHORITY`

`R72_NO_LOCAL_DELETION_FROM_EVIDENCE`

`R72_ENTRY_BLOCK_UNCHANGED`
