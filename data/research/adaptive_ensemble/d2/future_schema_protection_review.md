# Future-schema protection

TESTED. A document whose `schema_version` is an integer greater than 1 is classified `future` by `_version_kind`.

`initialise_fail_closed` returns through `_refuse_existing` and does not call the writer. The fixture bytes are unchanged after one read and after repeated reads. T09 and T11.

Effective authorisation is BLOCKED. The reason is `unsupported_future_schema`. No known strategy is active. T10.

A later call to `persist_evolve_disable` or either operator setter raises `SafetyStateProtected` and still does not replace the file. T11.

A boolean schema version is invalid, not future, because `bool` is a subclass of `int`. It is also left in place. T15.

The loader does not downgrade the version and does not treat the file as missing.
