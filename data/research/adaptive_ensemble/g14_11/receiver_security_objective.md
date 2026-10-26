# Receiver security objective

Invariant:

A future receiving workflow must not report successful receipt, verification, or publication unless the artifact bytes were written into an independently authorised filesystem object and stayed bound to that object through verification and publication.

A report of success on any weaker condition is a failure of the contract, even if the bytes hash correctly.

## Separate properties

These are not substitutes for each other.

| Property | What it means | What does not prove it |
| --- | --- | --- |
| A. Correct bytes | The receiver hashed bytes it read back from its own file handle. | A hash in a sender manifest. |
| B. Correct source | The bytes are tied to an approved index and artifact host. | A matching hash. No host is approved. |
| C. Correct receiving principal | The process token SID is the dedicated receiver SID. | A second process of the interactive user. |
| D. Correct filesystem object | The handle is the object the receiver created, and a same-user swap test has shown the interactive user cannot replace it. | A file id taken after `CreateFileW` on a caller-supplied path. |
| E. Correct publication destination | Publication stays on that same handle. | A rename into a directory the interactive user can open. |
| F. Correct dependency graph | `assert_dependency_graph` agrees on the received set, and the target profile is complete. | A lock file by itself. The profile is incomplete. |
| G. Correct target compatibility | Patch, SOABI, glibc, pip, and wheel tags are known and matched. | The tag `python:3.12-slim-bookworm` or the historical local image id. |
| H. Correct authorisation | A recorded approval covers this receipt. | A synthetic `COMPLETE_SYNTHETIC` result. |

## Threat the invariant is aimed at

The G.14.8 attacker is a same-user process that replaces the parent path before `CreateFileW`. The open then binds to the substitute. Later handle-relative writes are faithful to the wrong object. `os.lstat` before the open does not close that window. Post-open file identity does not recover the path that was intended.

The receiver contract forbids the sender from choosing that path. The receiver opens only a directory it created under its own principal. Bytes arrive as bytes. Success is refused while the principal, the ACL test, the source approval, or the target profile is missing.

## What this stage does not claim

No principal was created. No directory was created. No ACL was read or written. The invariant is a contract for a later implementation. It is not observed enforcement.
