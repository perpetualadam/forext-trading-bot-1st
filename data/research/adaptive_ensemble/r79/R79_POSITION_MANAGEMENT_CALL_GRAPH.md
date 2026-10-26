# R.79 Position Management Call Graph

Evidence class: static call chain from management entrypoints to the broker-write adapters. A check inside one entrypoint is not treated as a check for another.

| Path | Where | Authority check | Ownership and identity |
| --- | --- | --- | --- |
| Live position already open | `bot_loop.py` 796–802 | `live_management_permitted()` before profit protection and close logic | `position_management_permitted` refuses observation-only. Broker protection evidence is a trade-details read, not a write. |
| New broker entry | `bot_loop.py` around 1665, then `execute_oanda_market_open` | The cycle gate does not run when `pos is None`. `_submit_order_create` checks management permission before `claim_entry_permit`. | Entry permit, quote, exposure gate, and `record_entry_response` identity rules. |
| Guarded close | `broker_close_evidence.run_guarded_live_close` | Reaches `_submit_position_close_body`, which checks management permission before `claim_network_permit`. | Single trade id, live kind, durable `persist_bot_position`, account binding, and the close permit. |
| Profit protection | `profit_protection.apply_profit_protection` | No broker write in this function. The bot-cycle caller is behind the live-management gate. | R.71 constants unchanged. |
| Weekend flatten | `bot_loop.py` 784–793 | Blocks new entries in the flatten window. It does not flatten by itself in this branch. | Unchanged. |
| Reconciliation import | `positions.import_position_from_broker` | Does not enter the managed book. | Observation-only. |
| Paper `open_position` | `bot_loop.py` around 1941 and `positions.open_position` | No broker write. | Paper and synthetic kinds are manageable locally and are not a broker position. |
| Operator repair | `recovery_repair.repair_abandoned_recovery` | Does not publish and does not send an order. | Lock, owner token, process liveness, and an epoch increment. |
| Legacy helpers | `trading.execute_trade` live branch | Raises before HTTP. R.75 still expects that raise. | Not a management bypass. |

`_submit_order_create` and `_submit_position_close_body` are the write boundaries. A caller that skips them cannot reach `api.request` for those operations unless it uses `oanda_client._oanda_request`. Callers of `_oanda_request` are account, candle, pricing, pending-order, trade-detail, transaction-detail, open-position, and protection-detail reads.

No operational function submits a stop-loss replace, take-profit replace, trailing-stop replace, partial-close endpoint other than PositionClose units, OrderCancel, or OrderReplace. Local stop fields can change in memory and in the journal through `persist_protection_progress`. That is not a broker protection modification.
