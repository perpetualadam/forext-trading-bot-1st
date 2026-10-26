# R.83 recovery fencing review

Entry publication calls `recovery_fence_allows_publication` after the durable commit and before the book assignment. `test_04` changes authority with a real successor startup while the first process is inside that check. The first process prints `published=0`. The successor prints `manageable=1` and does not send a second OrderCreate.

Close removal now checks `current_fencing_epoch()` and `live_management_permitted()` before the pop. `test_07` runs a successor startup after a full confirmation and then calls removal from the stale process. Removal returns `None`. The journal remains `CLOSE_FULLY_CONFIRMED`. No second PositionClose is sent.

`test_14` increments the stored epoch from another connection. The close sink's authority read fails and PositionClose count stays 0.

Startup still clears and republishes only through `publish_recovered` while the successor's own startup holds the current epoch. A killed process has no further publication. No lease and no automatic takeover were added.
