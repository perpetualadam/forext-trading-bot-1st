# Exposure-release trust boundary

CODE MODIFIED in `confirm_exposure_flat`.

The previous function cleared the in-memory hold when the caller passed the string `CONFIRMED_FLAT`. That string is not broker-flat evidence.

The function now returns false for every caller-supplied value: the flat token, the word `verified`, `verified=True`, a dictionary, a fake reconciliation body, a wrong symbol, stale or incomplete data, and conflicting quantities. It does not read a broker and it does not remove the hold.

`interpret_close_evidence` still calls it and therefore also keeps the hold.

No production object can authorise a release. There is no offline success path. G41 and G87 are NOT_EVALUATED for that reason.

R.11 recovery selection is unchanged. A stored `CONFIRMED_FLAT` marker still changes which historical rows are selected. `finalize_order_fill` still writes `UNCONFIRMED`, not `CONFIRMED_FLAT`. The token can no longer be used as a function argument to drop a live hold.
