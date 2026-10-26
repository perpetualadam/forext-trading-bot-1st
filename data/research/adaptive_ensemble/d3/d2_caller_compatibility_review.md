# D.2 caller compatibility

`live_safety.py` was not modified. Its hash remains `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`.

## initialise_fail_closed

Signature unchanged. It does not raise for a future schema or corrupt JSON. The file is preserved and strategies are inactive. OFFLINE_TESTED. `app.py` ignores the return value and continues into database, broker, and background tasks. STATICALLY_VERIFIED. That continuation is the startup risk left by the non-raising D.2 contract. Changing it requires `app.py`, which was not authorised.

## SafetyStateProtected

`persist_evolve_disable` and both operator setters raise it for a protected file and do not replace the bytes. OFFLINE_TESTED. `bot_loop.evolve` already wraps `persist_evolve_disable` in `except Exception` and leaves the in-memory strategy inactive. STATICALLY_VERIFIED at `bot_loop.py` lines 1715-1720. A synthetic caller with the same catch was tested. `evolve` itself was not executed.

## Operator setters

Unconfirmed activation raises `PermissionError` and does not activate. Confirmed activation on a missing or valid file still works, then can be set back to inactive. Authorisation stays BLOCKED. OFFLINE_TESTED. On a protected file the setter raises before changing `active`.

## Order gate

`assert_new_live_exposure_allowed(action="open")` raises `RuntimeError` when the synthetic state is BLOCKED. OFFLINE_TESTED. Close actions are still exempt inside that function. Not exercised against a broker.

## Inspection

`live_order_auth_reason` reports `unsupported_future_schema` for an integer version above 1. OFFLINE_TESTED.

Caller compatibility of the running process and the historical image was not verified.
