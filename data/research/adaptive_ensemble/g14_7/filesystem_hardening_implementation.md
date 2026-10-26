# G.14.7 filesystem hardening implementation

## Destination rules

The workflow calls `assert_destination_boundary` before it opens a handle. That existing function rejects `..`, the repository, any path containing `OneDrive`, `concensus-forecast`, the staging directory, Docker volume fragments, and operational or shadow path segments. The repository check runs before the OneDrive check because the repository lives under OneDrive.

The child name is the fixed segment `g14-7-synthetic`. An existing child fails. A non-empty child fails with `destination_not_empty`. An empty existing child fails with `destination_exists`. The positive path creates the child with `FILE_CREATE` through the parent handle.

## Writes

`write_exclusive` uses `FILE_CREATE` and `FILE_NON_DIRECTORY_FILE`. An existing name returns `STATUS_OBJECT_NAME_COLLISION` and becomes `unsafe_file_replacement`. A link count above one becomes `hard_link`. A short write or a read-back that does not match the buffer becomes `interrupted_write` or `partial_download`. The partial file is not deleted.

Names already created through the same handle are compared case-insensitively. A second name that folds to an existing one fails with `case_collision`. `reject_member_name` still rejects the two sensitive backup filenames, `live_safety_state.json`, and any name that is not a single segment.

## Handle lifetime

File handles and both directory handles are closed when `run` finishes, including on failure. Closing a handle is not cleanup of the directory. A failed run does not remove the destination.

## Verification binding

Hash, ZIP, WHEEL, METADATA, RECORD, and dependency-graph checks use the bytes read from the file handle. The path-based `verify_wheelhouse` function remains for earlier tests and is not the completion path of this workflow.

## Platform results

| Case | Result |
| --- | --- |
| New empty destination | Created through the parent handle |
| Non-empty destination | `destination_not_empty` |
| Repository, OneDrive, staging, consensus-forecast, shadow path | Rejected before create |
| Real directory symlink | Not executed, errno 22 |
| Injected destination and parent link | Rejected |
| Real junction | `symlink_or_reparse` |
| Injected reparse attribute | `symlink_or_reparse` |
| Parent replaced after the handle was open | Writes stayed on the original object |
| Hard link at the target name | `unsafe_file_replacement` |
| Short write | `interrupted_write`, no lock, directory kept |
| Repeated run | `destination_not_empty` |
| `../` and `C:/` filenames | `path_traversal` |

## Classification

`ACQUISITION_FILESYSTEM_BOUNDARY_UNVERIFIED` for the initial path lookup. Post-open creates are handle-relative and were tested. This is not a claim that every Windows race is closed.
