# R.78 SQLite and filesystem review

`CloseJournal._configure` still sets `journal_mode=WAL` and `synchronous=FULL`, and refuses a different result. Schema 5 did not change those pragmas.

Transactions that matter for this stage:

- Entry finalisation remains one transaction in `commit_verified_entry`. That function was not edited.
- Recovery claim and epoch increment are one transaction in `_claim_run`.
- Repair audit, claim release, and epoch increment are one transaction in `_record`.
- `before_commit` rolls the repair transaction back. The claim remains in progress.

The unique partial index `one_recovery_in_progress` still allows one `RECOVERY_IN_PROGRESS` row. The OS lock is outside SQLite. A crash that kills the process releases the OS lock and leaves the SQLite row as it was at the last commit. WAL plus `FULL` makes that commit the durability boundary the code asks for. It does not prove the bytes survived power loss.

| Event | What was exercised | What was not |
| --- | --- | --- |
| Python exception before commit | repair fault injection | |
| Process kill via `os._exit` while holding the lock | the lock was releasable afterwards and repair committed | the SQLite page cache during power loss |
| OS crash | not performed | |
| Host reboot | not performed | Windows boot identity is a constant |
| Power loss | not performed | `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED` |
| Filesystem corruption | a non-SQLite file fails `open_journal` | silent corruption that passes `integrity_check` was not constructed |
| Journal replacement | a version-4 file does not open; a changed lock path refuses repair | |

Windows tests used the local temp directory. WSL tests used ext4 `/tmp`. The repository directory is 9p. Recovery-owner locks were not verified on 9p, SMB, or a network filesystem. Backup and restore of a live WAL journal were not tested. Copying a database without its `-wal` file is not a verified procedure.

Client ids stay in `entry_operations` and `client_order_id_registry`. Investigation rows are append-only and do not remove a client id.
