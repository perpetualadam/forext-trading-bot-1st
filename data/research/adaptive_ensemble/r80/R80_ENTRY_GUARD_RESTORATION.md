# R.80 entry-guard restoration

Evidence class: executed tests `test_04` through `test_11` and `test_13`. Synthetic broker only.

| Scenario | Result | Evidence |
| --- | --- | --- |
| Intent commits before the request | PASS | `test_04`. The durable reservation exists before the counted OrderCreate |
| One-shot permit | PASS | `test_04`. A second claim is refused. Calls stay `["OrderCreate"]` |
| Two processes cannot reserve one operation or one client id | PASS | `test_10`. One `reserved`, one `unresolved_entry_exists`, recorder 0 |
| Ambiguous transport does not retry | PASS | `test_04` raises after the call is counted and stays ambiguous. A second submit is refused |
| Journal failure after the synthetic submit | PASS | `test_05`. `ENTRY_OUTCOME_AMBIGUOUS`. Same client cannot be reserved again. One OrderCreate |
| Verified identity before memory publication | PASS | `test_07` republishes `T-TRADE` only after a real restart. `test_09` commits and then refuses memory publication when the epoch changes inside the request |
| Atomic finalisation | PASS | `test_07` |
| Duplicate client id refused permanently | PASS | `test_07` |
| Duplicate or wrong trade identity refused | PASS | `test_06` |
| Missing broker trade id cannot be managed | PASS | `test_06` order id equal to trade id is `order_id_is_not_trade_id` and is not finalised |
| Partial fill | PASS | `test_06` units 500. Not in memory |
| Mixed open and close effects | PASS | `test_06` `tradesClosed`. Not finalised |
| Failed memory publication does not undo the commit | PASS | `test_09`. Outcome `ENTRY_FINALISED`, memory absent, one OrderCreate |
| Restart recovers a committed finalisation | PASS | `test_07` |
| Restart does not promote an ambiguous entry | PARTIAL | `test_05` blocks a second reservation in the same process. A fresh startup over that ambiguous row was not asserted |
| Stale owner cannot submit | PASS | `test_08` and the successor in `test_11` |

`R80_ENTRY_ONCE_PRESERVED`: PASS.
`R80_ENTRY_AMBIGUITY_PRESERVED`: PASS.
`R80_CLIENT_ID_UNIQUENESS_PRESERVED`: PASS.
`R80_ATOMIC_ENTRY_FINALISATION_PRESERVED`: PASS.
`R80_STALE_OWNER_CANNOT_ENTER`: PASS.
