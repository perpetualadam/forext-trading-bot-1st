# Option A — trusted parent handle

Classification: `TRUST_ANCHOR_UNVERIFIED`

This is a design. Nothing in this section was implemented. No launcher was created.

## What the design would try to do

A process other than the acquisition workflow would open a parent directory and pass that handle in. The workflow would not call `open_directory` on a path. It would call the existing `DirectoryHandle.create_directory` and `write_exclusive` on the supplied handle. Those methods already use `NtCreateFile` with `RootDirectory` and `FILE_CREATE`.

`tests/g14_7_transport.py` `_validate_destination` would have to stop calling `open_directory(parent)` at the current call site. That change is described here and was not made.

## Root of the design

The launcher's own first open is the new root. On the evidence from G.14.8, that open is the same `CreateFileW` pathname lookup unless the launcher already holds a handle it did not obtain by looking up a path the same user can replace.

There is no such inherited handle in this process. The design therefore moves the vulnerable open from `open_directory` into the launcher. It does not remove it.

## Launcher authenticity

A launcher is not trusted because it is named a launcher. Trust would require all of the following, and none of them is evidenced:

- The launcher binary is the binary the operator invoked, not a same-user replacement of the executable path before `CreateProcess`.
- The launcher's token is not the token of the attacker who can rewrite the parent path.
- The handle it passes is the handle it opened, not a handle a same-user process substituted through process access.
- The directory object is a directory the attacker cannot have swapped before the launcher's open.

Process DACLs were not read. This stage does not claim that a same-user process can or cannot open the launcher with `PROCESS_DUP_HANDLE`. That specific access right is `API_CONTRACT_UNVERIFIED` here. The path-substitution result does not depend on it. G.14.8 already showed the swap against the open itself.

## Handle transfer

Two ordinary Windows mechanisms could be proposed later:

- Inheritance at process creation, if the parent marks the handle inheritable and creates the child itself.
- `DuplicateHandle` into a running process.

Both require the launcher to possess a good handle first. Inheritance also creates a new race on the child executable path. Duplication adds a race on which process receives the handle. Neither mechanism was called in G.14.8 or G.14.9. Neither is an evidenced fix.

## Identity after transfer

The existing helper can record volume serial and file index of whatever handle it is given. That check detects a later change of the handle's file id. It does not detect that the launcher opened the wrong object. G.14.8 recorded this as `PARTIALLY_VERIFIED` parent identity.

## Same-user attacker

If the launcher runs as the same user, that user can replace the launcher's parent path before its `CreateFileW`. The G.14.8 swap needed no administrator and no separate account. A same-user launcher does not change that result.

A launcher running as a different account could change it only if that account's directory is not writable by the acquisition user, the acquisition user cannot open the launcher process, and the first open performed by the other account is itself outside the acquisition user's write set. Creating that account would require administrator action. This stage did not create an account, did not request elevation, and did not read ACLs. That stronger launcher is unevidenced.

## Privilege

The weak design, a same-user launcher, does not need elevation and does not stop the demonstrated attacker.

The strong design needs a different security principal. That principal is not present in the evidence. Asking for it would be a separate approval, and it would still need its own proof that its first open is not exposed to the acquisition user.

## What could be reused

`DirectoryHandle.create_directory`, `write_exclusive`, `read_existing`, the reparse-attribute check, the volume-serial check, the reserved-name checks, and the closed-handle check could be reused behind a new entry point that accepts an already open handle.

`open_directory` could not be the trust anchor. `assert_destination_boundary` in `tests/g14_4_acquire.py` is a path walk and an `lstat`. G.14.8 case 2 showed that sequence does not bind the later open.

The G.14.7 verifier, which reads bytes from the file handle and checks the wheel, could stay. It verifies bytes on the opened object. It does not verify that the object was the intended directory.

The G.14.1 staging directory is a separate 63-file tree. Option A would not need to modify it. It also would not make that tree a trusted parent. Its path is still a path.

## Failure, crash, revocation, cleanup

The current helper already fails closed on a closed handle and on a create that returns an error after the directory is removed. Those properties are about the handle in hand. They do not revoke a handle that was wrong from the start.

A crash that leaves the handle open is an OS cleanup question this stage did not test. Cleanup of a wrong directory would be harmful if it deleted an attacker-chosen location, so a future design would still have to refuse deletion. The current code does not delete acquisition directories. That restraint should remain.

## Required evidence before this option could be reconsidered

- A principal that is not the acquisition user.
- A directory that principal creates, whose DACL denies the acquisition user write and delete, shown by a test that the acquisition user cannot replace the path.
- A handle transfer whose substitution is tested, not assumed.
- Proof that the launcher executable path is not itself replaceable by the acquisition user.
- The same post-open junction and rename tests, repeated against the transferred handle.

Until that evidence exists, Option A stays `TRUST_ANCHOR_UNVERIFIED`.

## Major risks

- The race moves one process earlier and remains.
- A same-user attacker who can influence process creation can replace the launcher as easily as the directory.
- A different-user design is an unevidenced privilege change.
- Success of handle-relative writes would still be reported against the wrong directory if the transferred handle is wrong.
- No network, Docker, or production-packaging change is required for the weak design, and that is not a reason to prefer it. The weak design fails the demonstrated threat.
