# R.78 test matrix

`PASS` means the named test executed the scenario. `NOT_VERIFIED` means the scenario was not faithfully produced.

| # | Scenario | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Valid single opened trade | PASS | `test_17` single |
| 2 | Order id differs from trade id | PASS | `O-ORDER` versus `T-TRADE` |
| 3 | Missing fill | PASS | `ENTRY_OUTCOME_AMBIGUOUS` |
| 4 | Multiple opened trades | PASS | `ENTRY_CONFIRMED_MULTIPLE_TRADES` |
| 5 | Partial fill | PASS | units 400, not manageable |
| 6 | Existing trade reduction | PASS | `tradeReduced` |
| 7 | Existing trade closure | PASS | `tradesClosed` |
| 8 | Order cancellation | PASS | `ENTRY_REJECTED_CONFIRMED` |
| 9 | Order rejection | PASS | `ENTRY_REJECTED_CONFIRMED` |
| 10 | Missing client id | PASS | `ENTRY_EVIDENCE_CONFLICT` |
| 11 | Conflicting client id | PASS | `ENTRY_EVIDENCE_CONFLICT` |
| 12 | Wrong account | PASS | `ENTRY_EVIDENCE_CONFLICT` |
| 13 | Wrong instrument | PASS | `ENTRY_EVIDENCE_CONFLICT` |
| 14 | Wrong direction | PASS | negative units |
| 15 | Wrong units | PASS | partial/mixed, not manageable |
| 16 | Missing related transaction id | PASS | valid fill still classifies from the fill |
| 17 | Conflicting retrieved transaction | PASS | `retrieved_fill_conflict` |
| 18 | Timeout after acceptance | PASS as journal state | outcome stays ambiguous; no second submit |
| 19 | Duplicate client id | PASS | reservation refused |
| 20 | Incomplete history | PASS | `snapshot_incomplete` |
| 21 | Missing historical transaction | PASS | `no_matching_evidence` |
| 22 | Unknown origin | PASS | quarantined |
| 23 | Manual trade | PASS | provenance other than `bot_managed` is quarantined |
| 24 | Broker-only trade | PASS | not manageable |
| 25 | Ambiguous close | PASS | repair does not change unresolved close rows and submits nothing |
| 26 | Active recovery owner | PASS | lock held, repair refused |
| 27 | Crashed recovery owner | PASS | `os._exit`, then `process_observation=dead` |
| 28 | PID reuse | PASS | current PID with a different start token can be released |
| 29 | Forged inactive evidence | PASS | `independent_liveness=lock_held` |
| 30 | Stale inactive evidence | PASS | timestamp method refused |
| 31 | Missing owner token | PASS | `process_not_proven_inactive` |
| 32 | Wrong owner token | PASS | `process_not_proven_inactive` |
| 33 | Restarted process with same PID | PASS as same-start refusal | a live PID with the recorded start is `recovery_owner_active` |
| 34 | Host boot identity changed | PASS as stored-id mismatch | `host_boot_identity_changed` |
| 35 | Journal moved | PASS as stored path hash | `journal_lock_path_changed` |
| 36 | Unsupported OS liveness | PASS as weak method | pid method refused before the lock |
| 37 | Liveness check failure | PASS | unreadable process status would be `process_status_unknown`; unknown caller status is refused |
| 38 | Owner exits during check | PASS | crash-owner test |
| 39 | Owner restarts during repair | NOT_VERIFIED | no process was restarted in the middle of the repair transaction |
| 40 | Two repair processes | PASS | exactly one commit |
| 41 | Two recovery processes | PASS | second startup blocked while the lock is held |
| 42 | Repair before claim release | PASS | active lock refuses |
| 43 | Repair after claim release | PASS | second repair is `recovery_claim_missing` |
| 44 | Old owner publishes after fencing | PASS | `recovery_fence_lost` |
| 45 | Old owner manages after fencing | PASS | `live_management_permitted` false |
| 46 | Fresh owner completes recovery | PASS | `test_12` |
| 47 | Fresh owner sees unresolved entry | PASS | startup quarantine path is unchanged; investigation does not clear it |
| 48 | Fresh owner sees unresolved close | PASS by repair count | repair does not finalise a close; startup was not given a new close-resolution path |
| 49 | Journal corruption | PASS | non-SQLite file refused |
| 50 | Schema mismatch | PASS | version 4 and version 3 do not open |
| 51 | Repair audit failure | PASS | `before_commit` leaves the claim |
| 52 | Recovery claim commit failure | PASS for the repair transaction | a failed claim insert releases the lock and does not leave a new in-progress row |
| 53 | Clock backwards | PASS | old and future timestamps do not authorise or block a lock-backed release |
| 54 | Clock forwards | PASS | same test |
| 55 | Operator acknowledgement missing | PASS | `operator_acknowledgement_required` |
| 56 | Repair attempts broker write | PASS as source and result | no order function, submission counts stay 0 |
| 57 | Repair enables source gate | PASS | gate hashes unchanged |
| 58 | Repair creates permit | PASS | no permit file |
| 59 | Recovery after committed repair | PASS | fresh startup reaches `RECOVERY_COMPLETED` |
| 60 | Recovery after interrupted repair | PASS | claim remains, then a later repair can run; the interrupted attempt itself does not start recovery |
| 61 | Linux Python recorded | PASS | 3.12.3 `/usr/bin/python3` |
| 62 | Linux SQLite recorded | PASS | 3.45.1 |
| 63 | Linux dependency inventory | PASS | five modules missing, `requests` present |
| 64 | Isolation before imports | PASS | `ISOLATION_READY` |
| 65 | `oanda_client` import | `IMPORT_BLOCKED_DEPENDENCY` | not a pass |
| 66 | `oanda_exec` import | `IMPORT_BLOCKED_DEPENDENCY` | not a pass |
| 67 | `bot_loop` import | `IMPORT_BLOCKED_DEPENDENCY` | not a pass |
| 68 | `startup_recovery` import | PASS | import only |
| 69 | `entry_journal` import | PASS | import only |
| 70 | `entry_capture` import | PASS | import only |
| 71 | `position_recovery` import | PASS | import only |
| 72 | `recovery_repair` import | PASS | import only |
| 73 | `reconciliation` import | `IMPORT_BLOCKED_DEPENDENCY` | not a pass |
| 74 | Synthetic journal bootstrap | PASS | Windows and WSL |
| 75 | Schema 5 open | PASS | version 4 refused |
| 76 | Atomic entry finalisation | PASS | R.77 suite except the version pin |
| 77 | Client-id uniqueness | PASS | duplicate reservation refused |
| 78 | Two-process entry reservation | PASS | R.77 overlapping reservation test still passed |
| 79 | Two-process recovery repair | PASS | Windows and WSL |
| 80 | Startup recovery | PASS | synthetic snapshot, Windows and WSL |
| 81 | Startup plus one actual cycle | NOT_VERIFIED | `bot_loop` did not import on Linux; the real cycle was not started |
| 82 | Management gate | PARTIAL | `live_management_permitted` ran on Linux; `_execute_bot_cycle` did not |
| 83 | Broker-only observation | PASS | not manageable |
| 84 | Ambiguous entry suppression | PASS | outcome unchanged, retry false |
| 85 | Ambiguous close suppression | PASS | repair submits no close |
| 86 | Profit-protection continuity | PASS | file hash unchanged, R.71 8 passed |
| 87 | No network connection | PASS | Linux import audit recorded 0 network attempts |
| 88 | No PostgreSQL connection | PASS | same audit; PostgreSQL was not opened |
| 89 | No source-gate change | PASS | gate hashes |
| 90 | No live permit | PASS | no `one_session.permit` |

Actual host reboot, power loss, and a real broker response are `NOT_VERIFIED` even where a stored-id or fixture stand-in passed.
