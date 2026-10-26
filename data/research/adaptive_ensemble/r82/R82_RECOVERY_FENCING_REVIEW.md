# R.82 recovery fencing review

Recovery authority is still a completed startup plus a fencing epoch read from `recovery_authority`. R.82 did not add lease expiry, automatic takeover, or a second owner protocol.

`test_10` and `test_11` run a real successor `execute_startup_sequence` while the first process is inside `api.request`. The successor becomes the process whose epoch matches the journal. The parent check then returns false. The request already in progress is the reproduced race. The next reservation is refused.

`test_14_ambiguous_entry_and_close_survive_restart` claims an entry permit and a close permit, then runs a fresh `execute_startup_sequence` with an empty book. The entry outcome is `ENTRY_OUTCOME_AMBIGUOUS`. The close state is `CLOSE_OUTCOME_AMBIGUOUS`. Write count is 0.

`test_08` and `test_09` delete the authority row during the rate-limit slot. The post-slot check refuses the request. A follow-up entry or close does not add a write.

Repair and owner-liveness behaviour from R.81 was not redesigned. The R.81 suite, which covers repair refusal while an owner is alive, passed again on Windows (16 tests, 28.179s) and Linux (16 tests, 35.671s).

Stale publication still depends on `live_management_permitted` and `recovery_fence_allows_publication`. R.82 did not patch either function to return true.
