# Safety-state forward compatibility

Classification: `FORWARD_COMPATIBILITY_DEFECT_CONFIRMED`.

This is a production blocker. The live safety file was not opened and not written.

## What the current source does

`forex_bot/live_safety.py` SHA-256 is `6e59666960dfec0ff379343c8973e389363faaab49278d9806c160a18ebe8f4f`. That is the G.7 hash, the G.10 hash, the G.13 working-tree hash, and the G.12 image sample hash. No later edit fixed it.

`SCHEMA_VERSION` is 1.

`_validate_document` accepts a document only when the version is 1, authorisation is BLOCKED or ALLOWED, and each of the six known strategy rows is a dict containing `active`. It returns that dict intact. Unknown top-level keys therefore survive validation.

`_snapshot_strategies_into` then replaces each known strategy row with a fixed set of keys: `active`, `authorised_for_live`, `disable_reason`, `changed_at_utc`, `sample_count`, `sharpe`, `loaded_from_durable`. Unknown keys inside a known strategy row are dropped.

`initialise_fail_closed` always calls that snapshot and then `_persist_unlocked`. Every successful startup rewrites the file.

If validation fails, including a newer `schema_version`, the function builds `_blank_document` and writes it. The blank document is BLOCKED, with six inactive strategies. The previous bytes are replaced.

Effective runtime authorisation is set BLOCKED even when the file says ALLOWED. The ALLOWED value in a valid file is not rewritten to BLOCKED by that path. The file can still say ALLOWED after a start. The process will not treat it as effective permission until an operator function changes runtime state. That split was not executed.

## Tests

G.13 recorded the same behavior from this hash. No test found in `tests/test_live_safety_repair.py` or `tests/test_decision_repair.py` asserts that unknown nested strategy keys survive a startup rewrite. Existing tests were not run.

## Rollback

Current code and the sampled image share this file. Rolling the image back to itself does not remove the behavior. Rolling forward to a newer schema, then starting this code, can discard the newer document. Rolling back after a newer writer has stored extra strategy-row keys will drop those keys on the next start of this code.

Older code can read a version-1 document that this writer emits, because this writer stays on version 1. It cannot safely read a newer version: it deletes it.

The historical durable reason `operator_preflight_blocked` was not confirmed by reading the file.
