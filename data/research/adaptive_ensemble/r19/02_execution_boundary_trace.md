# Gate A — actual execution-boundary trace

SOURCE-REVIEWED. The only `execute_oanda_market_open` occurrence in `forex_bot/bot_loop.py` is inside `production_execution_adapter`.

| Step | Function | Line | Caller | Eligibility | Reachable | Tested |
|---|---|---|---|---|---|---|
| Shared decision | `evaluate_one_instrument_iteration` | 3135 | offline harness | seals a decision, then uses FakeBroker when `simulation` is the isolated harness | yes, offline | runtime |
| Sealed decision | `_build_risk_decision` | 2834 | `_iteration_result` | records standing production gaps and registers a producer seal | yes | runtime |
| Production eligibility | same | 2902 | shared path | stays false while any mandatory gate is not PASS | yes | runtime |
| Reservation | `try_begin_order_submission` | shared path after eligibility | shared path | only after the synthetic dispatch block | yes, synthetic | runtime |
| Adapter selection | shared path | after reservation | shared path | simulation uses FakeBroker; production adapter is not called | yes | runtime |
| Production adapter | `production_execution_adapter` | 3010 | direct offline tests | `production_adapter_refusal` runs first | yes, offline | runtime |
| Broker call | `execute_oanda_market_open` | 3061 | adapter, only if refusal returns empty | unreachable while the producer cannot seal production eligibility | source only | substituted, zero calls |
| Argument map | `broker_open_arguments` | 2093 | adapter, only after a passing refusal | unchanged BUY positive / SELL negative units | helper tested; broker not called | runtime helper |
| Client and reservation ids | `_order_binding` | 2590 | decision builder | reservation id equals the client id only after a reservation attempt | yes | runtime |
| Legacy tail | anonymous broker tail | 1675 | `run_bot` path, not entered | logs `legacy broker tail is not a dispatch path` and returns | not entered | source-reviewed |

Other broker-open mentions in research and shadow modules were not edited and were not executed.

Exception, timeout, retry, and fallback: the adapter returns the refusal dict and does not await the broker. There is no retry loop. A prior `timeout`, `ambiguous`, `partial`, or `unresolved` outcome returns `prior_attempt_not_fresh`. The legacy `except OrderCreateCancelled` after the early return is unreachable.
