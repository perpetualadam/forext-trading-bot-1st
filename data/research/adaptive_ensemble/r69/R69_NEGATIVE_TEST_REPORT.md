# R.69 negative controls

Mutations stayed in the test process. Operational files were not edited.

| Control | Detection |
| --- | --- |
| Legacy insert of `reconcile_import` into `positions` with the flag false | `expect_unmanaged` raises `AssertionError: legacy reconcile_import row is in the managed book` |
| Predicate that treats kind `live` as enough | `assertFalse(weak(row))` fails because the weak predicate returns true. The real predicate returns false for the same flagged row |
| `position_management_permitted` replaced with a function that always returns true, then the real `_evaluate_impl` runs | `apply_profit_protection` is called for an observation row. The real guard test expects that call to be absent, so this mutation is visible |
| `positions.pop` instead of `close_position` | `expect_retained` raises `local row deleted`. The real `close_position` leaves the observation in the book |

Each control failed for the reason the ownership assertion is there to catch. A harness that only checked "no exception" would not have seen the legacy insert. The explicit state assertion does.
