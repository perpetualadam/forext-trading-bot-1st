# Mandatory-risk inventory

The shared function is `evaluate_one_instrument_iteration`. A call with `simulation=False` still returns at the live-permission gate. The record attached to every result separates a check that exists from a check that passed.

| Gate | Class | Production-default result | Blocks synthetic dispatch | Blocks production eligibility |
|---|---|---|---|---|
| Live permission | Mandatory now | BLOCK | No. The offline seam already requires the live gate to be closed. | Yes |
| Strategy gate for the injected test | Mandatory now | PASS only after the existing strategy gate | Yes, when the strategy gate blocks | The iteration gate can pass while production activation stays blocked |
| Production strategy activation | Mandatory now | BLOCK. Strategies stay inactive. | No | Yes |
| Position and exposure holds | Mandatory now | PASS only when no hold is present | Yes | Yes |
| AI vote | Mandatory now | PASS only for BUY or SELL | Yes | Yes |
| RL veto | Mandatory when invoked | PASS, or NOT_APPLICABLE with a reason when RL is not invoked | Yes, on veto | Yes, on veto |
| Isolated account snapshot | Mandatory now | PASS for a finite positive harness balance | Yes | The snapshot pass is not production authenticity |
| Production account provenance | Mandatory but lacking evidence | MISSING_EVIDENCE | No | Yes |
| Quote structure | Mandatory now | PASS for finite positive bid/ask with ask at least bid | Yes | Yes |
| Quote freshness | Mandatory now | PASS only when a timestamp meets the existing 90-second window | Yes. A missing timestamp is MISSING_EVIDENCE. | A harness PASS is not production freshness |
| Production quote provenance | Mandatory but lacking evidence | MISSING_EVIDENCE | No | Yes |
| Lookback | Mandatory now | PASS when the candle count meets the selector requirement | Yes | Yes |
| Production market provenance | Mandatory but lacking evidence | MISSING_EVIDENCE | No | Yes |
| Portfolio stop-risk | Mandatory now | PASS inside the existing 5% cap | Yes | Yes |
| Gross notional | Optional, conditionally enabled | DISABLED at percentage 0 | Only when enabled and breached or unreadable | A disabled gate is not a pass |
| Unit cap | Optional, conditionally enabled | DISABLED at 0 | Only when enabled and breached | A disabled gate is not a pass |
| Daily loss and drawdown | Optional, conditionally enabled | DISABLED while the flag is off | Only when the flag is on and the existing function blocks | A disabled gate is not a pass |
| Numeric spread | Mandatory but lacking policy | POLICY_UNAPPROVED | No numeric block was invented | Yes |
| Margin | Not implemented | NOT_IMPLEMENTED | No invented margin block on the synthetic contract | Yes |
| Reservation | Mandatory now | PASS only after the eligibility decision allows the isolated contract | A failed reservation does not run the adapter | A reservation is not production eligibility |
| Execution adapter | Mandatory now | BLOCK. The production adapter stays withheld. | The inert adapter is a separate synthetic fact | Yes |

A zero cap, an unapproved spread policy, and a missing margin implementation are not recorded as PASS.
