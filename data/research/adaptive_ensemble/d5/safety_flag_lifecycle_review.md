# Stage D.5 safety-flag lifecycle

`live_safety_initialised()` is true only when both `_initialised` and `_state_valid` are true.

Evidence level: ACTUAL_LIFESPAN_ISOLATED for the cases below. The flags were observed in the same process that executed `lifespan`.

| Phase | Flag result | Startup |
| --- | --- | --- |
| Before the first `initialise_fail_closed` | false | not started |
| Valid BLOCKED document | true after init | yielded |
| Persisted ALLOWED document | true, effective auth BLOCKED | yielded |
| Missing file, write succeeds | true, strategies inactive, auth BLOCKED | yielded |
| Corrupt JSON | `_initialised` true, `_state_valid` false, so the public flag is false | StartupSafetyAbort |
| Future schema | public flag false | StartupSafetyAbort |
| Invalid activation value | public flag false, strategies inactive | StartupSafetyAbort |
| Unreadable or permission error | public flag false, reason `safety_state_unreadable` | StartupSafetyAbort |
| Safety write `os.replace` fails | public flag false, reason `persistence_failure` | StartupSafetyAbort |
| Second call on an unchanged protected file | public flag stays false | StartupSafetyAbort |
| Successful init, then the file is replaced with corrupt JSON without `reset_live_safety_for_tests` | public flag was true before the second call and false after | StartupSafetyAbort |

A stale success flag does not bypass the guard. `initialise_fail_closed` inspects the file again and clears `_state_valid` on a protected file. `lifespan` checks the boolean after that call.

`SafetyStateProtected` is not raised by `initialise_fail_closed`. Later writers raise it. The lifespan protected path aborts with `StartupSafetyAbort` before those writers run.
