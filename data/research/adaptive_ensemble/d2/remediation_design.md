# Remediation design

The fix stays inside `forex_bot/live_safety.py`.

1. Classify the file before any write.
2. Missing path: create the existing blank BLOCKED document and write it atomically. Strategies in that document are inactive.
3. Version 1 document that passes validation: load it, keep unknown top-level keys, unknown strategy names, and unknown keys inside known strategy rows, then write the merged document.
4. Future integer schema, invalid JSON, wrong types, or an unreadable file: do not write. Effective authorisation is BLOCKED. Known strategies are set inactive in memory. `live_order_auth_reason` reports `unsupported_future_schema`, `corrupt_or_unreadable_state`, or `safety_state_unreadable`.
5. Later writers (`persist_evolve_disable` and both operator functions) raise `SafetyStateProtected` instead of replacing a protected file.
6. Known safety fields win over an unknown key of the same name. Unknown keys do not change `active` or authorisation.
7. `active` must be a JSON boolean. Anything else is an invalid document.

Startup code, the strategy registry, order routing, and the database were not changed. `Strategy.active` still defaults to True in `strategy_meta.py` until `initialise_fail_closed` runs. That remains a startup ordering limitation outside this module.

No new dependency, environment variable, or schema version was added. Version 1 documents written by the previous code still validate.
