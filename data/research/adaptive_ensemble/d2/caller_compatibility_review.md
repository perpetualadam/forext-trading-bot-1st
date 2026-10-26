# Caller compatibility

No caller module was modified. Signatures of `initialise_fail_closed`, `persist_evolve_disable`, `operator_set_live_order_authorisation`, `operator_set_strategy_active`, `live_open_blocked_reason`, and `assert_new_live_exposure_allowed` are unchanged.

Startup: `forex_bot/app.py` calls `initialise_fail_closed()` and does not catch its return value. A future or corrupt file no longer raises from that call, so lifespan does not crash on those files. A serialization `TypeError` can still propagate. Static inspection only. Lifespan was not executed.

Scheduler: `persist_evolve_disable` raises `SafetyStateProtected` when the file is future, invalid, or unreadable. `bot_loop.evolve` already catches `Exception` around that call and leaves the in-memory strategy inactive. Static inspection. `evolve` was not executed against a protected file in this stage.

Order routing: the gate functions were not given a new allow path. Effective authorisation on process start remains BLOCKED even when a valid file says ALLOWED. The existing repair test `test_persisted_allowed_starts_effective_blocked` passed.

Preflight: `inspect_safety_state_file` uses `_validate_document`. A future schema or a non-boolean `active` now fails that validation. `write_blocked_startup_document` still refuses to replace an existing path. Its own writer was not changed. The existing preflight overwrite test passed.

Integration of the running process, the historical image, and the live safety file was not performed. Those remain unverified.
