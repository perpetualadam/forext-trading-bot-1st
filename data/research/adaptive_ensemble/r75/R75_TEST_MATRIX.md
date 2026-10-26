# R.75 Test Matrix

Each row was executed by `test_r75_guard_and_recovery.py` unless noted. Close count is synthetic `PositionClose` requests. Delete is local deletion permission from the recovery decision or from the close path under test.

| # | Case | Durable state | Broker evidence | Recovered state | Management | Closes | Delete | Reason | Operator |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Clean journal, empty book | no rows | none | empty | no | 0 | no | none | no |
| 2 | Missing journal | file absent | none | not opened | no | 0 | no | `missing_journal` | yes |
| 3 | Corrupt journal | not a database | none | not opened | no | 0 | no | `corrupt_journal` | yes |
| 4 | Unsupported schema | version 99 | none | not opened | no | 0 | no | `unsupported_schema` | yes |
| 5 | Unacknowledged bootstrap | `closes_authorised=0` | none | reserve refused | no | 0 | no | `bootstrap_does_not_authorise_closes` | yes |
| 6 | Preexisting blocker | blocker row | none | reconciliation row returned | no | 0 | no | `preexisting_broker_position` | yes |
| 7 | Valid bot-owned row | complete `bot_managed` | matching trade | `restored_managed` | yes after publish | 0 | no | `broker_trade_matches` | no |
| 8 | Broker-only discovery | no row | discovery label | observation | no | 0 | no | `broker_only` | yes |
| 9 | Manual | provenance `manual` | matching shape | quarantine | no | 0 | no | `manual` | yes |
| 10 | Unknown kind | kind `mystery` | matching shape | quarantine | no | 0 | no | `unknown_execution_kind` | yes |
| 11 | Matching trade | complete row | same id, units, direction | managed | yes | 0 | no | `broker_trade_matches` | no |
| 12 | Wrong account | complete row | other binding | quarantine | no | 0 | no | `account_mismatch` | yes |
| 13 | Wrong instrument | complete row | other instrument | quarantine | no | 0 | no | `multiple_or_missing_trades` | yes |
| 14 | Wrong trade id | complete row | other id | quarantine | no | 0 | no | `trade_id_mismatch` | yes |
| 15 | Wrong direction | complete row | SELL | quarantine | no | 0 | no | `direction_mismatch` | yes |
| 16 | Changed units | complete row | 500 | quarantine | no | 0 | no | `units_mismatch` | yes |
| 17 | Multiple trades | complete row | two trades | quarantine | no | 0 | no | `multiple_or_missing_trades` | yes |
| 18 | Ambiguous close | row plus other instance | matching trade | quarantine | no | 0 | no | `journal_position_disagreement` | yes |
| 19 | Partial fill | covered by R.74 operational partial test, which passed | partial fill body | unresolved | no new submit | 1 original | no | partial confirmation | yes |
| 20 | Fully confirmed, not finalised | journal `CLOSE_FULLY_CONFIRMED` | n/a in recovery | `awaiting_finalisation` | no republish | 0 | no by recovery | `confirmed_close_not_finalised` | yes until finalise |
| 21 | Broker flat | complete row | `COMPLETE_EMPTY` | quarantine | no | 0 | no | `broker_flat_unattributed` | yes |
| 22 | Incomplete snapshot | complete row | `INCOMPLETE` | quarantine | no | 0 | no | `broker_snapshot_not_authoritative` | yes |
| 23 | Missing MFE | `max_profit_pips` NULL | matching trade | quarantine | no | 0 | no | `missing_management_state` | yes |
| 24 | Missing ratchet while active | activation 1, NULL exit fields | matching trade | quarantine | no | 0 | no | `missing_management_state` | yes |
| 25 | Missing take-profit | NULL | matching trade | quarantine | no | 0 | no | `missing_management_state` | yes |
| 26 | Missing stop | NULL | matching trade | quarantine | no | 0 | no | `missing_management_state` | yes |
| 27 | Replaced local position | instance A | matching A | not overwritten | existing row kept | 0 | no | `replaced_local_position` | yes |
| 28 | Generation conflict | generation 1 durable, local generation 4 | matching trade | not overwritten | local row kept | 0 | no | `replaced_local_position` | yes |
| 29 | Concurrent close | one unresolved claim | synthetic | second process refused | owner only | 1 | no | unique unresolved close | no |
| 30 | Recovery does not submit while a close exists | mixed rows | synthetic view | quarantine or unchanged | no extra close | 0 from recovery | no | disagreement or unchanged | yes when quarantined |
| 31 | Crash before durable write | no row | none | empty | no | 0 | no | nothing to restore | yes if a live fill existed only in memory |
| 32 | Crash after durable write | committed row, memory cleared | matching trade | restored | yes | 0 | no | `broker_trade_matches` | no |
| 33 | Crash before publish | same as 32 | matching trade | restored on next call | yes | 0 | no | `broker_trade_matches` | no |
| 34 | Crash after publish | row plus memory | matching trade | second call `unchanged` | yes | 0 | no | same instance | no |
| 35 | Duplicate instance | second insert same instance and other trade | n/a | insert refused | no | 0 | no | primary key | yes |
| 36 | Duplicate trade id | second instance, same trade | n/a | `duplicate_position_identity` | no | 0 | no | unique index | yes |
| 37 | Journal and position disagree | close instance differs | matching trade | quarantine | no | 0 | no | `journal_position_disagreement` | yes |
| 38 | Lookup timeout class | complete row | `REQUEST_FAILED` | quarantine | no | 0 | no | `broker_snapshot_not_authoritative` | yes |
| 39 | Malformed lookup class | complete row | `MALFORMED` | quarantine | no | 0 | no | `broker_snapshot_not_authoritative` | yes |
| 40 | Recovery twice | one row | matching trade | second result `unchanged` | yes | 0 | no | same identity | no |

Rows 19 and 20 also rely on the R.74 operational suite, which passed 9 tests on Windows. Row 29 is the two-process test. Rows 31–34 are process-state tests, not power-loss tests. The production loop does not call recovery by itself, so rows 7 and 32 describe `recover_managed_book`, not an automatic startup.
