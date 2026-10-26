# R.69 remaining risks

R.69 did not change trading behaviour. These items stay open.

| Id | Status |
| --- | --- |
| R66-03 | `broker_sl_tp_hit` still returns false. The live management test observed no stop-hit close from that function |
| R66-05 | Local fallback prices are still copied onto observations. They are not broker stops |
| R66-10 | A permitted live row is still removed when `auto_fix` sees a flat snapshot and trade details are not a full close. The test recorded `TradeDetails` and no `PositionClose` |
| R66-11 | An ambiguous live close can still be retried. No idempotency key was added |
| R66-16 | The books are still shared RAM. Two reconcile threads can run together. There is no lock across the gap between `get_position` and the ownership check. Observations did not become manageable in the tested interleavings |
| R66-01 | Production new entries remain blocked. The entry tail was not executed |
| R66-02, R66-06, R66-07, R66-08, R66-09, R66-12, R66-13, R66-14, R66-15, R66-17, R66-18, R66-19 | Outside this verification |

An OpenPositions body with no `positions` key is stored as an empty success. That does not grant management. It is not proof the broker book was read completely.

Clearing `observation_only` and setting kind `live` on an existing object makes the predicate true. No operational function does that. A future writer could.

C2, C3, and C4 remain design amendments. The close state machine and the protection parser are not implemented.

Production trading remains NO-GO.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

`POSTGRESQL_INTEGRATION_NOT_TESTED`
