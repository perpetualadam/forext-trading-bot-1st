# Atomic write

The writer renders JSON before opening the temporary file. The temporary path is the target path plus `.tmp`, in the same directory. The write flushes and `os.fsync`s the temporary file, then `os.replace`s it onto the target. On failure the temporary file is removed when it exists, and the exception propagates.

TESTED:

- A successful save leaves parseable JSON. T21.
- A serialization `TypeError` leaves the original bytes. T22. That error escapes `initialise_fail_closed`, because only `OSError` is caught there.
- A temporary-file open failure and an `os.replace` failure leave the original bytes. `initialise_fail_closed` catches the `OSError`, stays BLOCKED, and does not leave a partial target. T23, T24, T25.

Durability limit: this is not a power-loss proof. The parent directory is not fsynced. Windows crash behaviour of `os.replace` was not tested. Do not treat the change as full crash durability.
