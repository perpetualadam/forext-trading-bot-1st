# R.70 Diff Review

## Operational diff

`forex_bot/reconciliation.py`

- Original SHA-256: `f938807b59c2089767fdf69e4cf7d74671ffe62d74e5853169812ffe438a0bbf`
- Final SHA-256: `df67cc020986e0056b4bf3bea6fbbd9947090741cafa8793a4ac57660a0b9165`
- Size: 37010 bytes

Added:

- `threading` and `Decimal` imports.
- `BrokerSnapshotError`.
- `_parse_broker_decimal`, `_interpret_open_positions`, `_begin_snapshot_request`, `_publish_snapshot`.
- Generation fields `_snapshot_lock`, `_snapshot_generation`, `_accepted_generation`, `_last_snapshot_class`, `_fetch_tls`.

Changed:

- `fetch_broker_positions_detail` validates and publishes, and raises instead of returning an invented empty book.
- A missing client raises `UNKNOWN` in every mode, including paper. Previously a skipped fetch could look like a flat book.
- `reconcile_positions_log_only` classifies fetch failures and skips convergence when the fetch raises.
- The snapshot dictionary gains `broker_snapshot_class`.

Not changed:

- Case A–E structure.
- `import_position_from_broker` ownership behaviour.
- `auto_fix` rules for a valid book.
- Close-result parsing.
- Position-sizing and stop formulas.

## Research diffs

`data/research/adaptive_ensemble/r70/poc/test_r70_snapshot.py` is new.

- SHA-256: `393e3972d2d3da07d67c684cfdaa6a040867f4ed755e9f801475b3df0bdf031c`
- Size: 20112 bytes

`data/research/adaptive_ensemble/r69/poc/test_r69_integration.py` was updated so the existing suite matches the stricter contract.

- SHA-256: `42c98ee68d12d2e995a792d3354844179dce03c06724cd20e7482ad1f0c94060`
- Size: 33750 bytes
- `test_10` now expects `INCOMPLETE` and `_have_broker_snapshot is False`.
- `test_12` now expects `CONFLICT` and no observation.
- The operational hash pin for `reconciliation.py` is the R.70 digest. The other three pins remain the R.68 digests.
- `_payload` places a negative net on `short.units` as a negative string. The previous helper placed the absolute value on the short side, which the new sign rule correctly rejects.

The R.69 isolation harness was not edited. Its SHA-256 remains `b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54`.

## Review conclusions

- The patch does not add a broker write, a database table, or an execution grant.
- Invalid evidence fails before destructive convergence.
- Valid empty evidence is still destructive for a permitted live row. That is disclosed.
- Direct use of `_remember_broker_snapshot` can still replace the book without a generation check. Reconcile's success path does not call it.
- Stored units are `float` after a `Decimal` validity check.
