# Safety-state contract

`initialise_fail_closed` at `live_safety.py` line 383 always sets effective authorisation to BLOCKED. A persisted ALLOWED value does not become effective authorisation.

`_version_kind` treats a missing or non-integer schema version as invalid, a higher version as future, and the supported version as current. Corrupt, future, unreadable, and invalid files go through `_refuse_existing`. That function leaves the file bytes unchanged, deactivates strategies, sets BLOCKED, sets `_initialised` true, and sets `_state_valid` false. `live_safety_initialised()` therefore stays false, and lifespan raises `StartupSafetyAbort`.

`_preserve_unknown` keeps keys that are not in the known set. `_atomic_write` writes a sibling temporary file, flushes, fsyncs, and uses `os.replace`. An `OSError` from persist sets `_state_valid` false and BLOCKED. The isolated replace failure left `live_safety_initialised()` false and removed the temporary file.

`operator_set_strategy_active` and `operator_set_live_order_authorisation` require `operator_confirmed=True`. They are not called by lifespan. `Strategy.active` stores true only when the assigned object is boolean True.

The isolated valid document left all six original strategies inactive. An explicit confirmed `active=True` activated one strategy in the temporary file, and a confirmed false restored it. No production safety file was opened.
