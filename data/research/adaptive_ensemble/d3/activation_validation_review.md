# Activation validation review

OFFLINE_TESTED on the strategy object:

- `False` stays inactive.
- Boolean `True` is stored as active. This is the explicit assignment used by the existing operator setter.
- `None`, `"true"`, `"false"`, `1`, `0`, `[]`, `["scalp"]`, and a plain object stay inactive.
- The setter does not call `bool(value)`.

OFFLINE_TESTED on synthetic safety documents through `initialise_fail_closed`:

- A missing `active` field leaves the file unchanged and leaves every known strategy inactive.
- The string `"false"` on a known row does the same.
- Corrupt JSON and an integer schema version above 1 do the same.
- A BLOCKED document stays BLOCKED.

STATICALLY_VERIFIED: persisted documents are accepted only when `live_safety._validate_document` sees a real boolean `active`. That module was not edited. Its D.2 tests were re-run and passed.

`live_safety._empty_strategy_record` still wraps its default with `bool(active)`. Its default argument is `False`, and the startup blank document uses that default. No change was made there.
