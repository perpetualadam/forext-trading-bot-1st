# G.14.8 Windows API contract review

No network documentation was retrieved. Contracts below are limited to what this process observed or to flags present in `tests/g14_7_fs.py`. Unused APIs are not given a contract.

## Used

`CreateFileW` is called once per trusted parent, with `OPEN_EXISTING`, `FILE_FLAG_BACKUP_SEMANTICS`, and `FILE_FLAG_OPEN_REPARSE_POINT`. A junction opened this way was rejected because `GetFileInformationByHandle` reported `FILE_ATTRIBUTE_REPARSE_POINT`. A directory symlink was not created, so that flag's symlink behavior is not a verified contract.

`NtCreateFile` is called with `RootDirectory` set to an already open directory, a relative name, and disposition `FILE_CREATE` (2). Directories also pass `FILE_DIRECTORY_FILE`, `FILE_SYNCHRONOUS_IO_NONALERT`, and `FILE_OPEN_REPARSE_POINT`. Files pass `FILE_NON_DIRECTORY_FILE` and `FILE_SYNCHRONOUS_IO_NONALERT`. Status 0 produced a usable handle. Status `0xC0000035` was translated to `destination_exists` or `unsafe_file_replacement`. Other statuses become `handle_create_failed`. The full NTSTATUS table is `API_CONTRACT_UNVERIFIED`.

`OBJECT_ATTRIBUTES.Attributes` is 0. `OBJ_CASE_INSENSITIVE` is not set. Whether the filesystem lookup is case-sensitive is `API_CONTRACT_UNVERIFIED`. The helper rejects a second name that differs only by case before calling the API.

Sharing is `FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE` (7). With that share mode, `os.rmdir` removed a child directory while its handle was open. The next `NtCreateFile` on that handle failed closed. This observation is not a general deletion contract.

`GetFileInformationByHandle` supplied the volume serial, file index, attributes, and link count used by the helper. `WriteFile`, `ReadFile`, `SetFilePointer`, and `CloseHandle` behaved as the existing read-back and close tests require on this 64-bit process. 32-bit structure layout was not tested and is `API_CONTRACT_UNVERIFIED`.

The `UNICODE_STRING` buffer is the Python string passed to the call. The helper rejects empty names, separators, and `..` before the call. Pointer lifetime is the duration of `NtCreateFile` only.

## Not used

`NtQueryInformationFile`, `GetFileInformationByHandleEx`, `GetFinalPathNameByHandleW`, `GetFileAttributesW`, `FILE_OPEN`, and `FILE_OPEN_IF` are not on the workflow path. `FILE_OPEN` is defined and unused. No final path is consulted, because a path string is not treated as identity.

## Handle ownership

`open_directory` and `create_directory` return a `DirectoryHandle` that closes the kernel handle once. `write_exclusive` returns a file handle that the workflow closes. On a rejected identity check, the new handle is closed before the exception leaves the helper.
