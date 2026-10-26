# R.79 Broker-Write Sink Audit

Evidence class: static search for request constructors and `api.request`, plus synthetic interceptor tests. No sink was called against OANDA.

| Sink | Location | Guard before `api.request` | Can startup, repair, or a legacy helper call it? |
| --- | --- | --- | --- |
| `oanda_orders.OrderCreate` | `oanda_exec.py` 541–547 | Entry permit type, `live_management_permitted()` at 506–509, exposure gate, quote, then `claim_entry_permit`. The authority check is before the one-shot claim. | Startup and repair do not call it. `execute_oanda_market_open` and `_place_market_order_open_sync` do. |
| `oanda_positions.PositionClose` | `oanda_exec.py` 446–453 | Close permit type, `live_management_permitted()` at 411–415, then `claim_network_permit`. | Reached from `run_guarded_live_close`. Repair does not call it. |
| `TradeClose` | No submit function | Not present | No |
| `TradeCRCDO` | No submit function | Not present | No |
| `OrderCancel` | Parsed from a PositionClose response at `oanda_exec.py` 478. Not submitted. | Response handling only | No |
| `OrderReplace` | No submit function | Not present | No |
| Stop, take-profit, trailing replace | No submit function. OrderCreate can attach `stopLossOnFill` and `takeProfitOnFill` on the entry request. | Same OrderCreate guard | Only as part of the guarded entry |
| `_oanda_request` | `oanda_client.py` 291–301 | Retries transient read failures. Callers listed in the management report are reads. | A future caller could pass a write object. No current caller does. |
| `trading.execute_trade` live | Raises before HTTP | Live safety refusal | Legacy helper |
| Alternate HTTP client | `urllib.request.urlopen` is blocked by isolation during tests. Operational code uses the oandapy client. | Isolation is a test control, not the production guard. | Not a production write path |

`test_06` constructed real entry and close permit objects with no recovery session. Both adapters raised before `request`. `test_07` and `test_16` reached exactly one OrderCreate after recovery, and the synthetic request raised or the journal fault prevented finalisation. `test_15` reached exactly one PositionClose after recovery and refused a second permit.

An unguarded operational write path was not found. The residual race is the gap between the authority read and `api.request`, documented in the authority-loss review.
