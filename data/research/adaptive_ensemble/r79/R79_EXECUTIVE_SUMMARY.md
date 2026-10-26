# R.79 Executive Summary

Classification: `R79_LINUX_OPERATIONAL_VERIFIED_OFFLINE`

Production trading remains **NO-GO**. R.80 was not started.

The actual `forex_bot.bot_loop.run_startup_and_one_iteration` function ran on Linux and on Windows against a synthetic broker. The wrapper called the real `_execute_bot_cycle`. Both platforms completed 17 R.79 tests. Linux imported all 18 requested operational modules after a disposable virtual environment was created outside the repository.

Operational position publication now fails closed when the fencing epoch is missing or the recovery session is not in progress or completed. Offline reconstruction stays on `recover_managed_book`, which does not grant live management. Entry and close broker writes re-check `live_management_permitted()` before a one-shot permit is consumed.

Previously green R.75 close tests, the R.74 operational close suite, and several R.76 entry tests now fail because they submit without a recovery session. Those failures are obsolete expectations. With a completed recovery, one close still confirms and a stale close permit is refused, one ambiguous entry submit is not repeated, and a stored profit-protection ratchet is not lowered.

## Explicit answer

Can the actual operational startup and one-cycle path now execute safely on Linux using a synthetic broker, and is every operationally reachable position-publication, management and broker-write path protected by valid recovery and ownership authority?

| Evidence | Answer |
| --- | --- |
| Source implementation | Startup claims the owner lock and assigns an epoch before publication. A missing epoch returns false from `recovery_fence_allows_publication`. OrderCreate and PositionClose check `live_management_permitted()` before permit consumption. |
| Static call graph | Operational publication writers are `publish_recovered` and the post-commit branch of `record_entry_response`. `recover_managed_book` is offline-only. The only `api.request` write sinks are OrderCreate and PositionClose. No TradeCRCDO, OrderCancel, or OrderReplace submit function exists. |
| Offline test execution | Windows: 17 R.79 tests passed. Null epoch, stale epoch, blocked recovery, intercepted OrderCreate, and authorised close-once were executed. |
| Actual Linux operational execution | Disposable CPython 3.12.3 imported the operational modules and passed the same 17 tests. The real cycle set `last_bot_cycle_utc`. No broker write succeeded. |
| Multiprocess execution | A second process holding the OS lock blocked startup. R.78 two-repair and crashed-owner tests passed on Linux. Two-process close and entry races that expected a broker write without recovery now stop before the request. |
| Broker protocol assumptions | Order id is not trade id. Client-id idempotency is not documented by OANDA. `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED` remains. |
| Real broker execution | Not performed. `REAL_NETWORK_EXECUTION_NOT_TESTED` remains. |
| Unverified behaviour | The check immediately before `api.request` does not remove the race between that check and the socket write. Power-loss durability, PostgreSQL, and data-only mode remain unverified. |

## Acceptance criteria

| Criterion | Result |
| --- | --- |
| R79_BASELINE_VERIFIED | PASS |
| R79_SOURCE_GATES_UNCHANGED | PASS |
| R79_DISPOSABLE_LINUX_ENVIRONMENT_CREATED | PASS |
| R79_DEPENDENCIES_REPRODUCIBLE | PARTIAL |
| R79_LINUX_OPERATIONAL_IMPORTS_PASSED | PASS |
| R79_ISOLATION_VALIDATED | PASS |
| R79_ACTUAL_STARTUP_FUNCTION_EXECUTED | PASS |
| R79_ACTUAL_BOT_CYCLE_EXECUTED | PASS |
| R79_STARTUP_PRECEDES_MANAGEMENT | PASS |
| R79_FAILED_RECOVERY_BLOCKS_MANAGEMENT | PASS |
| R79_INCOMPLETE_SNAPSHOT_BLOCKS_MANAGEMENT | PASS |
| R79_POSITION_PUBLICATION_PATHS_ENUMERATED | PASS |
| R79_OPERATIONAL_PUBLICATION_REQUIRES_AUTHORITY | PASS |
| R79_NULL_EPOCH_CANNOT_BYPASS_OPERATIONAL_FENCE | PASS |
| R79_LEGACY_RECOVERY_BOUNDARY_VERIFIED | PASS |
| R79_MANAGEMENT_PATHS_ENUMERATED | PASS |
| R79_BROKER_WRITE_SINKS_ENUMERATED | PASS |
| R79_BROKER_WRITES_REQUIRE_GUARDS | PASS |
| R79_AUTHORITY_LOSS_FAILS_CLOSED | PARTIAL |
| R79_STALE_OWNER_CANNOT_PUBLISH | PASS |
| R79_STALE_OWNER_CANNOT_MANAGE | PASS |
| R79_CONCURRENT_RECOVERY_SAFE | PASS |
| R79_CONCURRENT_REPAIR_SAFE | PASS |
| R79_SCHEMA5_INTEGRITY_PRESERVED | PASS |
| R79_R77_ATOMIC_ENTRY_PRESERVED | PASS |
| R79_R77_CLIENT_ID_UNIQUENESS_PRESERVED | PASS |
| R79_R76_ENTRY_GUARD_PRESERVED | PASS |
| R79_R75_CLOSE_GUARD_PRESERVED | PASS |
| R79_R74_JOURNAL_PRESERVED | PASS |
| R79_R71_PROFIT_PROTECTION_UNCHANGED | PASS |
| R79_NO_REAL_BROKER_REQUEST | PASS |
| R79_NO_POSTGRESQL_CONNECTION | PASS |
| R79_NO_CREDENTIAL_ACCESS | PASS |
| R79_NO_PRODUCTION_JOURNAL_ACCESS | PASS |
| R79_NO_LIVE_PERMIT | PASS |

`R79_DEPENDENCIES_REPRODUCIBLE` is PARTIAL because `requirements.txt` uses minimum versions. The disposable install recorded exact wheels and SHA-256 hashes, but a later install can resolve newer wheels.

`R79_AUTHORITY_LOSS_FAILS_CLOSED` is PARTIAL because authority was removed before a later cycle and before publication, and the write adapters refuse when management is not permitted. A fault injected while a broker read is in flight, and a second process repairing during `api.request`, were not executed.
