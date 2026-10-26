# Restart boundary

Both scenarios used the real offline `evaluate` path, then the existing offline startup recovery, then `evaluate` again. The maps were emptied between the two calls. The JSON file was the only surviving order state.

## FILLED

Application instance A selected `scalp`, called the inert adapter once, and recorded `FILLED` with `exposure_safety=UNCONFIRMED`. The file is `stores/filled.json`, SHA-256 `e6594e518dc92ca2d4953a1f33e39ec1669276e68e64f2e7b6789872b55cc987`.

Instance A was discarded: orders, positions, reservations, and exposure maps were all zero, and the file hash was unchanged.

Fresh startup called `initialise_application`, which read the file and ran `select_rows_for_recovery` then `ingest_recovery_snapshot`. The rebuilt order is a new object with `source=db_recovery` and status `FILLED`. Exposure was `exposure_unconfirmed`.

Instance B called `evaluate`, made no reservation, and made no adapter call. It stopped with `exposure_unconfirmed`. Production eligibility stayed false.

## UNRESOLVED

Application instance A called the inert adapter once and recorded `UNRESOLVED` with the same unconfirmed exposure marker. The file is `stores/ambiguous.json`, SHA-256 `f2e1924aef6fb54160cb738ba2d1bd8ff420180783d632ea42b48afb0f2e79a2`.

The maps were cleared. Startup recovered status `UNRESOLVED` through the same two functions. Instance B called `evaluate`, did not reserve, did not dispatch, and did not retry. It stopped with `exposure_unconfirmed`.

This restart is inside one interpreter. The module-level maps were destroyed and rebuilt. A second operating-system process was not started. PostgreSQL was not contacted.
