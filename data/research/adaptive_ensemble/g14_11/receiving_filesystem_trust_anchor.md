# Receiving filesystem trust anchor

Classification: `RECEIVING_DIRECTORY_TRUST_ANCHOR_UNVERIFIED`

Nothing in this document was created. No directory, ACL, label, or owner was changed.

## Proposed root

The root is a directory the receiver account creates, then opens itself, then never reopens by a path supplied by the sender. The handle from that open is the only parent for child creation. Child files use `FILE_CREATE` relative to that handle, which is the pattern already in `tests/g14_7_fs.py` `create_directory` and `write_exclusive`.

That pattern is necessary and not sufficient. G.14.8 showed it is faithful to whatever object the first open returned. The first open is safe only when the interactive user cannot replace the path before the receiver's `CreateFileW`. This stage does not claim that condition holds.

## How the design answers the G.14.8 race

The design uses option C from the stage brief: it does not take the attacker's path.

- The sender does not pass a directory path.
- The sender does not pass a directory handle. A handle from the interactive user is untrusted. `DuplicateHandle` from that user is not an anchor.
- The receiver opens a path that only its own account was supposed to create.
- If a future test shows the interactive user can still replace that path, the receiver stays in `FAILED_CLOSED` and accepts nothing.

Option A, "the ACL prevents substitution", is the hoped mechanism and is not evidenced. Option B, "detect and fail closed", is mandatory when identity, owner, or the substitution test is missing. `lstat` then `CreateFileW` is not the detector. A file id after the open is not the detector.

## The 25 boundary points

1. Root anchor: receiver-created directory plus the handle the receiver opened. Not verified.
2. Ownership: receiver SID. Not read, because the directory does not exist.
3. Directory ACL: must deny the interactive user's write, delete, and take-ownership while that user is medium integrity. Not written.
4. Parent ACL: the parent must also deny those rights. Otherwise the race moves up one level.
5. Ancestors: every ancestor the interactive user can rename is still a substitution point. Not enumerated.
6. Same-user write: must fail in a future test. Not tested.
7. Same-user delete: must fail. Not tested. G.14.8 `os.rmdir` succeeded against a directory this user owned while a handle was open. That result must not be repeatable against the receiver directory.
8. Same-user rename: must fail. This is the G.14.8 swap.
9. Directory replacement: must fail before the receiver's open, or the receiver must not be started.
10. Junction insertion: the receiver rejects an open that returns `FILE_ATTRIBUTE_REPARSE_POINT`, as the helper does. A junction the attacker cannot create in the parent is the ACL claim, unverified.
11. Directory symlink: G.14.8 `os.symlink` failed with errno 22. Still not a kernel result. The receiver must treat a reparse attribute as failure. It must not claim symlink behaviour was tested.
12. Other reparse tags: not enumerated. Attribute rejection is the design. Tag coverage is a future test.
13. Hard links: `write_exclusive` rejects link count above 1 at create. A later hard link is a new open and must be rejected again by the consumer of bytes, not by trusting the path.
14. Volume identity: child volume serial must match the parent handle. A cross-volume case was not executed in G.14.8.
15. File identity: volume serial and file index of the opened object. Not proof of pre-open intent.
16. Handle lifetime: the receiver keeps the directory handle until publication is refused or the bytes have been re-read for the consumer. Close ends the claim.
17. Handle transfer: handles are not accepted from the sender.
18. Child creation: `FILE_CREATE` on the directory handle only.
19. Exclusive create: existing names fail. Case-folded collisions fail before the second create.
20. Writes: `WriteFile` on the new file handle, then read-back, as `write_exclusive` does.
21. Verification: `verify_member_bytes` on those read-back bytes. Not on a path scan.
22. Publication: a state flag on the receiver. Not a rename into the interactive user's tree.
23. Crash: an incomplete publication stays unpublished. Leftover files under the receiver directory are not a success and are not silently deleted by a broad cleanup.
24. Cleanup: no deletion of the 63-file staging tree, G.14.7 probe directories, production files, or historical evidence.
25. Independent verification: the receiver's own hash. The sender manifest is a claim.

## Same-user ACL limit

An owner can change a discretionary ACL on an object they own. The design therefore requires the interactive user not to own the directory. G.14.8 recorded `ACL_RESTRICTION_NOT_APPLICABLE` for that owner and `ACL_RESTRICTION_UNVERIFIED` for the bytes of any DACL. A read-only attribute is not this boundary.

If the interactive account can elevate, it may be able to take ownership later. G.14.10's deny-only Administrators SID makes that a live question. It was not tested. The design does not claim administrator resistance.

## Classification

`DESIGNED_NOT_IMPLEMENTED` and `RECEIVING_DIRECTORY_TRUST_ANCHOR_UNVERIFIED`.

Implementation stays blocked until a future approval creates the principal and a medium-integrity substitution test fails closed without touching production.
