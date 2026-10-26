# G.14.8 findings preserved for G.14.9

This review does not reclassify Stage G.14.8. The historical result remains `G14_8_FILESYSTEM_HARDENING_PARTIAL_GATE_B_BLOCKED`. The recorded test result remains 225 passed, 0 failed, and 3 skipped. Ruff and Mypy were recorded as passed in that stage. G.14.9 did not re-run them.

## Critical observation

`tests/g14_7_fs.py` function `open_directory` calls `CreateFileW` on the caller-supplied path. `tests/g14_7_transport.py` `_validate_destination` calls that function on the parent path, then `create_directory` relative to the returned handle.

G.14.8 cases 1, 2, 3, and 11 showed that a same-user replacement before that open makes the handle refer to the substitute. The child directory and a file were created there. The workflow did not fail closed.

Cases 4, 5, and 8 showed the opposite timing: after the handle exists, renaming the path or placing a junction at the old path does not move later writes. That is a property of the opened object. It is not evidence that the opened object was the intended directory.

`HANDLE_RELATIVE_OPERATIONS_VERIFIED_WITH_ASSUMPTIONS` therefore does not mean `FILESYSTEM_TRUST_BOUNDARY_VERIFIED`.

## Preserved findings

1. The initial parent open is path-based.
2. The caller-supplied parent path is not a trusted anchor.
3. A same-user process can replace that path before `CreateFileW`. No extra privilege was required.
4. The opened handle then refers to the substitute.
5. A child can be created in the substitute.
6. Later handle-relative writes stay bound to the opened object.
7. That binding does not prove the object was intended.
8. No inherited trusted parent handle exists.
9. Volume serial and file index identify the opened object only. They do not recover a pre-open identity.
10. The initial path race remains `INITIAL_PATH_RACE_UNVERIFIED`.

## Additional findings that stay open

- Junction rejection was tested on this machine, both before and after the open.
- Real directory-symlink creation returned errno 22 and was not counted as a pass.
- Reparse tags other than the tested junction were not enumerated.
- A real cross-volume create was not executed. The volume-mismatch predicate is not a kernel result.
- Directory ownership and DACL bytes were not read.
- A same-user ACL is not a demonstrated control against that same user.
- `DEFAULT_TRANSPORT` is `NETWORK_DISABLED`. A real HTTPS sender is absent.
- `https://pypi.org/simple` and `files.pythonhosted.org` are not approved and were not contacted.
- Target compatibility remains incomplete.

## What this stage will not treat as a fix

Another `os.lstat` before `CreateFileW` does not close the race. G.14.8 case 2 opened the substitute after the stat. A file id does not prove the path still named the intended object, because the id is taken from whichever object the open returned. Path-string equality has the same limit: the substitute can keep the path the caller asked for.
