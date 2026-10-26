# R.73 Reconciliation Interaction

`account_disappeared_broker_position` (`broker_exit.py` lines 571–586) still returns `observation` for a non-permitted row before any flat handling.

For every other row it records `broker_flat_not_close_confirmation` and returns `retained` unless a fully confirmed close operation already exists. It does not pop the row and it does not change the operation state.

`reconciliation.py` lines 697–704 do not count `retained` as a consumed auto-fix. The OpenPositions classifier is unchanged: `{}` is still `INCOMPLETE`, and `{"positions": []}` is still `COMPLETE_EMPTY`. An incomplete body still skips the flat branch. A complete empty body may call the helper, and the helper now keeps the live row.

The old pop-on-unresolved-lookup code remains only after `live_local_delete_permitted` is already true.

`R73_BROKER_FLAT_NOT_TREATED_AS_CLOSE_CONFIRMATION`

`R73_RECONCILIATION_PRESERVES_UNRESOLVED_CLOSE`

`R73_R70_SNAPSHOT_CONTRACT_PRESERVED` for classification. The historical test that expected the empty snapshot to delete the row now fails. That test was not edited.
