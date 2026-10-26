# G.14.8 directory-handle identity

## What is checked

After `CreateFileW` or a directory `NtCreateFile`, `GetFileInformationByHandle` must succeed. The handle is rejected when `FILE_ATTRIBUTE_REPARSE_POINT` is set. The recorded identity is the volume serial number plus the 64-bit file index (`nFileIndexHigh`, `nFileIndexLow`).

Before a later create or write, the same query is repeated. A closed handle fails with `handle_closed`. A changed identity would fail with `handle_identity_changed`. That second check confirms the handle still refers to the object that was opened. It does not prove the opened object was the one the caller named before the race window.

A new directory must have the same volume serial as its parent handle. A new file must too, and it must not be a reparse point. The positive test observed equal volume serials and different file indexes for a parent and its child. A mismatched pair is rejected by `_require_same_volume`. No second volume was mounted, so a real cross-volume transition was not produced. That negative kernel case is not claimed.

## What is not identity

Path equality is not used. `GetFinalPathNameByHandleW` is not called. Ownership and ACL are not read from the handle. The file index is not treated as a globally unique id across volumes; the volume serial is the scope observed here.

## Classification

Child identity relative to an already opened parent handle: `PARTIALLY_VERIFIED`.

The initial parent handle's correspondence to the caller's intended directory: `DIRECTORY_HANDLE_IDENTITY_UNVERIFIED`.
