# Confirmed defect analysis

Status labels: CONFIRMED means the pre-change source did this. TESTED means a D.2 test now covers the corrected behaviour.

## Nested-field loss

CONFIRMED before the edit. `_snapshot_strategies_into` replaced each known strategy row with a fixed set of keys. Unknown nested keys were dropped on every startup rewrite. TESTED after the edit by T05 and T06.

## Unsupported schema overwrite

CONFIRMED before the edit. Any `schema_version` other than 1 failed validation, and `initialise_fail_closed` then wrote a blank BLOCKED document over the file. TESTED after the edit by T09, T10, and T11. The original bytes stay in place.

## Corrupt-state overwrite

CONFIRMED before the edit. Invalid JSON took the same replacement path whenever the path existed. TESTED after the edit by T12, T13, T14, T15, T16, T17, and T18. Those files are not replaced.

## Activation interpretation

CONFIRMED before the edit. `bool(row.get("active"))` treats any non-empty string, including `"false"`, as active. TESTED after the edit: a non-boolean `active` makes the document invalid, the file is kept, and the strategy stays inactive.

## Atomic-write weaknesses

CONFIRMED before the edit. The writer used a temporary file and `os.replace` without flush or fsync, and a failed render could not be distinguished from a successful replace. The replacement is still `os.replace`. Flush and fsync of the temporary file were added. TESTED: T21 through T25. Full power-loss durability is not claimed. Directory fsync is not available as a tested Windows guarantee.

## What was already safe

Unknown top-level keys on a valid document were already retained, because the loader returned the parsed dict and only replaced the strategy map. That behaviour is kept and is now regression-tested by T03 and T04.

A missing file is still distinct from a bad file. A missing file gets a new BLOCKED document. A permission error does not. TESTED by T19 and T20.
