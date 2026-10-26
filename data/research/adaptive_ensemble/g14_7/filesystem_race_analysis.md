# G.14.7 filesystem race analysis

## Prior gap

G.14.6 checked `os.lstat` and then created files by path with `O_EXCL`. A parent directory could be replaced between the check and the open. `FILESYSTEM_RACE_STATUS` stayed `ACQUISITION_FILESYSTEM_BOUNDARY_UNVERIFIED`. That historical finding is unchanged.

## What this stage changed

`tests/g14_7_fs.py` opens an existing directory once with `CreateFileW`, using `FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT`. If the handle's attributes include `FILE_ATTRIBUTE_REPARSE_POINT`, the open is rejected.

Later creates use `NtCreateFile` with that handle as `RootDirectory`, disposition `FILE_CREATE` (exclusive), and a single path segment. The relative name is rejected when it contains a separator, a drive colon, or `..`. The workflow then reads the new file through the same file handle. `verify_member_bytes` uses those bytes. It does not call `verify_wheelhouse`, which still walks a directory by path for the older tests.

## What the tests showed

A deterministic replacement, not a timing test, renamed the opened destination and created a new directory at the old path before the write. The wheel and `synthetic-lock.json` were in the renamed directory. The replacement directory was empty.

A real directory junction created with `mklink /J` inside a pytest temporary directory was rejected with `symlink_or_reparse`.

`os.symlink` for a directory failed with errno 22. Those two tests were skipped and are not passes. Injected `os.lstat` results for a destination link, a parent link, and a reparse attribute were rejected by the workflow. A hard link planted at the wheel name was rejected with `unsafe_file_replacement`. A short `WriteFile` was rejected with `interrupted_write`, the destination directory was left in place, and no lock file was written.

## What remains unverified

The first `CreateFileW` is still a lookup by path. After it returns, the handle is checked and later operations use that object. A different non-reparse directory substituted for the parent name before `CreateFileW` returns would be the object the handle is bound to. This process has no POSIX `openat` directory-descriptor API to remove that initial lookup. Python's Windows `os` module was not treated as providing one.

Because that initial window remains, this stage does not say the parent-directory replacement race is eliminated. The post-open write path is bound to the opened object in the test above. The initial lookup stays `INITIAL_PATH_LOOKUP_NOT_ATOMIC`, and the boundary classification stays `ACQUISITION_FILESYSTEM_BOUNDARY_UNVERIFIED`.

No path-based write fallback was added. If `NtCreateFile` fails, the workflow fails closed.
