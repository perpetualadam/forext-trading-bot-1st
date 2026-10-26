# G.14.8 handle-relative directory creation

The workflow already creates `g14-7-synthetic` with `NtCreateFile` and `RootDirectory` set to the parent handle. G.14.8 did not replace that with a path-based create.

Sequence that the code performs:

1. `assert_destination_boundary` on the path. This is not the trust anchor.
2. `CreateFileW` on that path. This is the unresolved lookup.
3. Reject the handle if it is a reparse point, and record its file identity.
4. `FILE_CREATE` the child name relative to that handle.
5. Reject an existing name. Exact duplicates reach `FILE_CREATE` and become `destination_exists`. A different case becomes `case_collision` first.
6. Keep the child handle, require a matching volume serial, and reject a reparse result.
7. Write and read files relative to the child handle.
8. Write the synthetic lock relative to the same handle.

The parent handle is retained until `run` finishes. The workflow does not reopen the child by path and does not fall back to `open` or `shutil`.

## Limitation

Creating the child relative to the parent moves the pathname lookup to step 2. It does not remove it. The pre-open replacement test created the child on the substitute directory. The trust anchor is still that first opened object, and it is not independently established.

`HANDLE_RELATIVE_DIRECTORY_CREATION_UNVERIFIED` is not the result for the child create itself. The child create is handle-relative and was tested. The chain of trust is unverified because the parent anchor is unverified.
