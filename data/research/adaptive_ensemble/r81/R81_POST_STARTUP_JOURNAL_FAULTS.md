# R.81 post-startup journal faults

Evidence class: executed `test_15`, plus the rate-limit and crash tests for the surrounding windows. Not every Phase I point was given its own fault injection.

| Fault | Executed result |
| --- | --- |
| Authority loss before the permit claim | PASS. `test_10` fences the owner before it reserves or claims. No request |
| Authority loss after the permit claim, during the rate-limit wait | PASS. `test_02` and `test_03`. Permit stays consumed. Request count 0 |
| Journal unavailable after rate-limit acquisition, as a separate connection failure | NOT_VERIFIED. The executed post-slot fault is authority loss, not a dropped journal file |
| Journal failure after synthetic acceptance | PASS. `test_15` counts one OrderCreate, arms `before_commit`, and leaves `ENTRY_OUTCOME_AMBIGUOUS`. The fresh process does not submit |
| Journal failure during close confirmation or protection persistence | NOT_VERIFIED as a separate injection. Close timeout and crash tests leave the close unresolved |
| Entry finalisation atomicity on the success path | PASS. `test_04` reaches `ENTRY_FINALISED` and a second client reservation is refused |

No production journal was opened. A failed commit does not become permission for a second request.

`R81_POST_STARTUP_JOURNAL_FAULTS` coverage is PARTIAL against the full Phase I list and PASS for the rows above that were executed.
