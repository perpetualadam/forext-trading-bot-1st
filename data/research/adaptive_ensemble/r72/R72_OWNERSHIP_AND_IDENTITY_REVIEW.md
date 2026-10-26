# R.72 Ownership and Identity Review

`position_management_permitted` is unchanged in `forex_bot/positions.py` lines 56–69. `collect_broker_protection_evidence` calls it before any broker read (lines 429–430). A false result returns `management_not_permitted` and does not change `observation_only`.

| Row | Result |
| --- | --- |
| Paper, simulated, window_paper, synthetic | No broker read. Reason `local_reference_not_broker_evidence`. |
| Permitted live, one trade id | TradeDetails is requested. |
| `reconcile_import` and `import_position_from_broker` | Observation stays observation. Not inserted into `positions`. |
| `observation_only=True` on a live-labelled row | Refused. No request. |
| Unknown kind | Refused. No request. |
| Missing trade id | Unknown. No request. |
| Two trade ids on one row | `multiple_trade_ids`. No request. Orders are not merged. |
| Order `tradeID` different from the local trade | `PROTECTION_CONFLICT` (`order_trade_mismatch`). |
| Instrument on the trade different from the local symbol | `trade_identity_mismatch`, unknown, not published as protection. |

Discovering a protective order does not grant management. The R.68 functional tests passed apart from the historical `live_manage.py` hash pin.

`R72_OBSERVATION_MANAGEMENT_REFUSED`

`R72_R68_OWNERSHIP_PRESERVED`
