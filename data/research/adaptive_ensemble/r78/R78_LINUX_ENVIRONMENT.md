# R.78 Linux environment

Inspected through WSL without installing packages or reading secrets. Access date 2026-10-25.

| Item | Value |
| --- | --- |
| Distribution | Ubuntu 24.04.3 LTS (Noble Numbat) |
| Kernel | `Linux NucBoxM5PLUS 6.6.87.2-microsoft-standard-WSL2` |
| Python | 3.12.3, `/usr/bin/python3`, GCC 13.3.0 |
| Platform | `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39` |
| Virtual environment | none. `VIRTUAL_ENV` empty. No repo `.venv` was used |
| SQLite | 3.45.1 |
| Temporary directory | `/tmp` |
| `/tmp` filesystem | ext4 on `/dev/sdd` |
| Repository mount | `/mnt/c`, type `9p` |
| Windows runner used for the same tests | CPython 3.13.5 |

SQLite compile options relevant to WAL include `DEFAULT_WAL_AUTOCHECKPOINT=1000`, `DEFAULT_WAL_SYNCHRONOUS=2`, `THREADSAFE=1`, `MUTEX_PTHREADS`, and `ENABLE_UNLOCK_NOTIFY`. `PRAGMA journal_mode=WAL` on `:memory:` returns `memory`. On a file under `/tmp` it returns `wal`. `PRAGMA synchronous=FULL` returns `2`, which is SQLite's numeric value for `FULL`.

The repository on `/mnt/c` is a 9p mount. R.78 tests did not put journals there. Windows tests used the user temp directory. WSL tests used `/tmp` on ext4. Lock behaviour on 9p or SMB is not a verified guarantee.

Platform-dependent recovery code is `forex_bot/recovery_owner_lock.py`:

- Windows lock: `msvcrt.locking` `LK_NBLCK` / `LK_UNLCK`, lines 33–36 and 52–55.
- Linux lock: `fcntl.flock` `LOCK_EX|LOCK_NB` / `LOCK_UN`, lines 38–40 and 56–58.
- Linux process start: `/proc/<pid>/stat` field 22, with zombie state `Z` treated as dead, `_linux_start` lines 121–137.
- Linux boot id: `/proc/sys/kernel/random/boot_id`, `host_boot_id` lines 77–89.
- Windows process start: `OpenProcess` plus `GetProcessTimes`. A non-zero exit time means the process has exited, `_windows_start` lines 140–176.
- Windows boot id: the constant `windows:boot-id-unavailable`. A Windows reboot is not detected.

No production journal, `.env`, or credential was read.
