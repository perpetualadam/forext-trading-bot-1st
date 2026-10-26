# Safety-state API map

`live_safety.py` was not modified. Hash `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`.

## Public results app.py can use

- `initialise_fail_closed()` loads or refuses. It does not raise for a protected file.
- `live_safety_initialised()` is true only when `_initialised` and `_state_valid` are both true. Line 88.
- `live_order_auth_reason()` returns a reason code, not the document.
- `live_order_auth_state()` is the effective authorisation. Process start forces BLOCKED even when a valid file says ALLOWED.
- `live_safety_snapshot()` exposes `strategy_state_valid`, which is the same validity flag.

## How the cases map

| Case | After initialise_fail_closed | Startup |
| --- | --- | --- |
| Valid supported BLOCKED | initialised true, effective BLOCKED | continue |
| Valid supported with persisted ALLOWED | initialised true, effective BLOCKED | continue, no new grant |
| Missing file, write succeeds | initialised true, new BLOCKED document | continue |
| Corrupt JSON | initialised false, reason `corrupt_or_unreadable_state` | abort |
| Invalid document | initialised false, same corrupt reason | abort |
| Future schema | initialised false, reason `unsupported_future_schema` | abort |
| Unreadable or permission error | initialised false, reason `safety_state_unreadable` | abort |
| Persist OSError on a supported document | initialised false, reason `persistence_failure` | abort |
| Any other non-valid result | initialised false | abort |

Corrupt JSON and an invalid version-1 document share one reason code. Both are not startup-compatible, and both leave the file unchanged. The abort does not need to tell them apart.

The decision in `app.py` uses `live_safety_initialised()`. It does not match reason text to decide whether to continue.

This is sufficient. No change to `live_safety.py` is required for the abort.
