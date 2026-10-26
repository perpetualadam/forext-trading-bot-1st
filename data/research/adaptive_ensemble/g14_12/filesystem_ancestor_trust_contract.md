# Filesystem ancestor trust contract

No receiving directory exists. No path below is approved. No rename test was performed. This is the placement rule a later approval would have to meet before any artifact is accepted.

## Forbidden roots

The interactive user's temporary directory, the OneDrive project directory, the repository root, the 63-file staging directory, a system directory used as a wheel dump, and any production, operational, or shadow mount are not candidates. A user-owned ACL is not a boundary against that user. A pre-open `lstat` is not a boundary. A file index taken after `CreateFileW` is not proof the path was the intended one. A read-only attribute is not a boundary. A SHA-256 match is not a boundary.

## Required chain

For a path that does not exist yet, every component from the volume root through the receiving directory must satisfy all of the following before the receiver opens it. If any item is unknown, the state is `FAILED_CLOSED`.

1. Volume: the receiver records the volume serial of the directory handle after a successful open. A later child whose serial differs fails. Which volume may be used is not chosen here.
2. Volume security: not inspected. BitLocker or other volume encryption is unknown and is not claimed.
3. Root ownership: not the interactive SID `S-1-5-21-1451533663-3497457457-3930589332-1001`.
4. Root DACL: that SID has no write, delete, or control rights listed below.
5. Parent ownership: the receiver SID, once that account exists. It does not exist.
6. Parent DACL: same deny list for the interactive SID.
7. Receiving-directory ownership: the receiver SID.
8. Receiving-directory DACL: same deny list, plus the receiver SID may create children until publication rules say otherwise.
9. Inherited ACEs: an inherited grant of write to the interactive SID or to Everyone fails the contract. Inheritance must be inspected, not assumed.
10. Explicit ACEs: the contract is the effective access, not the presence of a single deny entry. A deny that is overridden by a broader allow fails.
11. Deny ACEs: a deny alone is not the proof. Effective access for the interactive medium token must be none of the rights below.
12. Owner rights: owner is the receiver SID. Owner-rights that grant the interactive user control fail.
13. WRITE_DAC: denied to the interactive SID on every ancestor and on the directory.
14. WRITE_OWNER: denied to the interactive SID on every ancestor and on the directory.
15. DELETE: denied to the interactive SID.
16. DELETE_CHILD: denied to the interactive SID on every ancestor.
17. FILE_ADD_FILE: denied to the interactive SID.
18. FILE_ADD_SUBDIRECTORY: denied to the interactive SID.
19. Reparse-point creation: denied. An open that returns the reparse attribute fails closed even if creation was not supposed to be possible.
20. Junction creation: same. G.14.8 showed this user can create a junction in a directory they can write. That is why write is denied. Not retested here.
21. Symlink creation: same rule. Kernel symlink behaviour remains unexecuted from G.14.8. Absence of a successful symlink test is not a pass.
22. Directory rename: denied on the directory and on every ancestor.
23. Directory replacement: a medium-integrity attempt to replace any component must fail before the receiver's `CreateFileW`. If it succeeds, the design is withdrawn.
24. Mount-point redirection: a mount point is a reparse point and fails the attribute check. Not separately tested.
25. File-ID stability: the file index is recorded and compared. It is not identity by itself.
26. Volume-ID stability: the volume serial is compared. A cross-volume create fails.
27. Handle lifetime: the receiver keeps the directory handle from open through the consumer send. Close ends consumability for that session.
28. Handle transfer: handles from the interactive user are refused.
29. Time-of-check/time-of-use: the sender never supplies the path, so the sender cannot win the receiver's open race unless an ancestor is replaceable. The ancestor test is the control. It has not been run.
30. Post-open mutation: G.14.8 showed later creates stay on the opened object. That remains useful and does not prove the first open.
31. Publication-path mutation: there is no second path. The commit is a file created on the open handle.
32. Build-consumer path mutation: the consumer receives bytes, not a path.

## Future evidence that would establish the chain

A later approval would have to show, without using production paths:

- The receiver SID owns the directory.
- Effective access of the interactive medium token lacks every right in items 13 through 22 on the directory and each ancestor.
- A rename or replacement attempt by that token fails, and the substitute receives no file.
- The receiver's own open still refers to the original file index.

Until those exist, the anchor is `RECEIVING_DIRECTORY_TRUST_ANCHOR_UNVERIFIED`.

## Claim limit

This contract is aimed at the observed medium-integrity same-user attacker and at other unprivileged users who are actually denied by the DACL. It does not claim resistance to an elevated administrator, a compromised host, or a compromised receiver. G.14.10 showed this process is not elevated. It did not show the account cannot elevate.
