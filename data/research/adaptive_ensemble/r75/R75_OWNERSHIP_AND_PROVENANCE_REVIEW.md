# R.75 Ownership and Provenance Review

R.68 remains in force. `import_position_from_broker` still writes `broker_observations` and does not assign `positions[symbol]`. `position_management_permitted` still accepts only paper, simulated, window_paper, live, and synthetic, and still rejects `observation_only`.

R.75 adds `recovery_quarantine` to that refusal (`positions.py` lines 70–71).

| Provenance or kind | Function | Managed book | Close authority |
| --- | --- | --- | --- |
| `bot_managed` plus a complete matching broker trade | `evaluate_durable_row` | May be published | Not granted by recovery |
| `bot_managed` with missing protection or an incomplete ratchet | `evaluate_durable_row` | Quarantine | Refused |
| `manual` | `evaluate_durable_row` or `classify_broker_discovery` | Not published | Refused |
| `broker_only` or any non-`bot_managed` discovery | `classify_broker_discovery` line 401 | Not published | Refused |
| unknown execution kind | `evaluate_durable_row` | Quarantine, reason `unknown_execution_kind` | Refused |
| observation import | existing R.68 import | `broker_observations` only | Refused |

`classify_broker_discovery("bot_managed")` returns `not_a_discovery` / `durable_record_required`. A broker discovery is never upgraded because the string says bot-managed. The durable row has to already exist.

`persist_bot_position` refuses a position that fails `position_management_permitted`, an observation row, an unknown kind, a missing instance, or any trade-id count other than one (`trade_identity_unresolved`).

Tests: `test_recovery_matrix` checks discovery classification and an empty `positions` dict. `test_missing_protection_and_unknown_origin_are_quarantined` checks manual, mystery kind, and NULL protection, and asserts the managed book stays empty.
