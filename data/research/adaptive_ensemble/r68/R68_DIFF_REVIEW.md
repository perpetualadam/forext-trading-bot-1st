# R.68 diff review

Operational files changed: four. No formatting-only rewrite. No dependency change.

## `forex_bot/positions.py`

| Item | Effect |
| --- | --- |
| `Position.observation_only` | Default false, appended so existing constructors keep their current fields. |
| `broker_observations` | Side record of discoveries. `get_position` does not read it. |
| `position_management_permitted` | Single ownership predicate. |
| `import_position_from_broker` | Writes `broker_observations` only. Forces `reconcile_import` and `observation_only=True`. Leaves an existing managed row in place. |
| `close_position` | Returns none and leaves the row when the predicate is false. Permitted rows still pop. |
| `close_local_position` | Uses `close_position`. |
| `adjust_position_units_to_broker` | Returns false without mutation when the predicate is false. |

SHA-256 before `e63ac07e6677ae5707a2a75888bcd5c39df5957ab34547659546e8546d537f2a`. After `129101e45bafbe0b3359127b3f6e4cf49721a18da1c76301d8d86968218207d5`.

## `forex_bot/reconciliation.py`

| Item | Effect |
| --- | --- |
| Case B | Logs the paper-versus-broker conflict, records an observation, and does not call `displace_paper_position`. |
| Case C | Still calls `_import_broker_truth` for the existing read and local price copy. Does not increment `fixes`. The import no longer inserts a managed row. |
| `auto_fix` loop | Continues past rows that fail `position_management_permitted` before disappear or unit adjust. Permitted live rows keep the previous auto-fix path. |

SHA-256 before `295686792ab017cfc8dfba8fd0add6b2b66a3008304ade141e899af7e86e776b`. After `f938807b59c2089767fdf69e4cf7d74671ffe62d74e5853169812ffe438a0bbf`.

## `forex_bot/bot_loop.py`

The positions import now includes `position_management_permitted`. Inside `if pos:`, a false predicate logs `observation_only_position` and returns before the existing manage tail.

The production entry block and `production_path_has_no_simulation_context` were not edited. Quote, profit-protection, weekend, and sizing formulas in this function were not edited.

SHA-256 before `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796`. After `51023112554b2b6989ade50994a822aeb6e1968df58e513ad00ded820820ec51`.

## `forex_bot/broker_exit.py`

`account_disappeared_broker_position` returns `observation` before any pop when the resident row fails the predicate. Permitted rows still follow the previous pop and booking path. No order call was added.

SHA-256 before `d9920eed6160c5f26e1db7ee34095488b3457755e5dbf21cffbeda08eb798c12`. After `bcdc3e04908208f8c397acb291eceae19fca5dc78028a6914269d409cc53474c`.

## Unchanged operational hashes

| Path | SHA-256 |
| --- | --- |
| `forex_bot/execution.py` | `6602e363171e3aac4bc4b597ddb805c454c7ca40f7d1fe3fddf542f6a1ab86e2` |
| `forex_bot/trading.py` | `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7` |
| `forex_bot/live_manage.py` | `60d87b8665620743467832758032857e975d32da15322307a0c331009cc7b25d` |
| `forex_bot/oanda_exec.py` | `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8` |
| `forex_bot/profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |
| `forex_bot/app.py` | `1883d3c94a570b66782b7079bcd64d7657c83c0cd6faa385cab7a65bc2d56bd1` |
| `forex_bot/database.py` | `be83fc2a485af0f392203562a8286082587b0824f235557b6036e69f661f840d` |
| `main.py` | `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb` |

## After-change reachability

| Path | Result |
| --- | --- |
| `log_only` / broker-mode Case C | Observation record only. Managed book unchanged. |
| `auto_fix` | Does not disappear or resize a non-permitted row. |
| Forged `execution_kind="live"` on an observation | Predicate false. No `PositionClose` from the manage prefix. No local pop. |
| Manual broker discovery | Stays in `broker_observations`. |
| Paper row beside a broker observation | Paper row kept and still permitted. |
| Bot-opened `live`, `simulated`, `window_paper`, or `synthetic` with `observation_only` false | Predicate true. Existing pop and manage tail remain for that row. |
| Unknown kind | Predicate false. Row kept. |
