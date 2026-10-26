# Database failure modes

| Case | Result in this stage | Evidence |
| --- | --- | --- |
| Persistence off or recovery unreadable | SYNTHETICALLY TESTED. New reservation refused. | `test_h10_h12` |
| Unknown or corrupt recovery row | SYNTHETICALLY TESTED. Fail closed. | `test_h09_h11` |
| Process fail-closed flag | SYNTHETICALLY TESTED. Reservation refused. | `test_h13_h16` |
| Query raises on a live connection | NOT_EVALUATED | No engine |
| Commit fails | NOT_EVALUATED | Source returns False after rollback. Not executed |
| Rollback fails | NOT_EVALUATED | Not executed |
| Connection drops before commit | NOT_EVALUATED | Not executed |
| Ambiguous commit | NOT_EVALUATED | Source treats the exception as failure. A committed PENDING row would not block another client id. Not executed |
| Duplicate client id in memory | SYNTHETICALLY TESTED | `test_h01_h06` |
| Empty recovery treated as permission | The unreadable path does not. An empty readable list is a different case and was not given a live database |

No database error in the synthetic tests was treated as permission to send a broker order. No broker order function was called.
