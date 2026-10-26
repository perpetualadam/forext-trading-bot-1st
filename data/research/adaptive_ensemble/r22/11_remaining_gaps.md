# Remaining gaps

- The JSON file is an offline substitute. PostgreSQL was not started, and production durability was not tested.
- The restart ran in one interpreter. The maps were cleared and the recovered order is a new object, but the process itself was not recycled.
- Recovered state covers orders and exposure. The local position book is not rebuilt from the store, so a filled restart blocks on exposure rather than on a restored position.
- `CONFIRMED_FLAT` remains an internal token. No broker reconciliation was performed.
- Production eligibility remains false.
- The historical R.10 `WinError 5` on that stage's safety-state file did not occur here. The limitation is not closed.
