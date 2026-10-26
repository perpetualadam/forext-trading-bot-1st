# G.14.8 trusted-parent threat model

## Assumed attacker

The attacker can run another process as the same Windows user that runs the tests. That process can rename directories the user owns, create a directory junction in a directory the user can write, and win a pathname lookup. The G.14.8 pre-open swap did this inside the test process without an administrator privilege and without changing a system ACL.

The attacker cannot be assumed to be unable to modify a user-owned temporary directory. A discretionary ACL on an object the user owns can be rewritten by that user. This stage did not query or change any ACL.

## Inside the model

- Accidental replacement of a path before `CreateFileW`.
- Same-user rename or junction insertion before the first open.
- Replacement or junction insertion after a handle exists.
- Reparse points on the object that was opened.
- Ambiguous file names: traversal, alternate-data-stream syntax, reserved device names, trailing dots, and trailing spaces.
- Use of a handle after it has been closed.
- Removal of a directory while its handle is still open.

## Outside the model

- An attacker who can modify this process's memory or execute arbitrary code in it.
- An administrator who can install a driver, attach a debugger, or replace the process.
- A claim that a different user's ACL denial was tested. It was not.
- A claim that every reparse tag was enumerated. It was not.

## Trust anchor

There is no externally supplied trusted directory handle. The first trusted-looking object is whatever `CreateFileW` returns for the caller-supplied path. That object is then identified by volume serial and file index, and later creates use `NtCreateFile` with that handle as `RootDirectory`.

The anchor is a handle-bound directory object only after the open succeeds. It is not a private directory, a restricted-ACL directory, or an OS-provided trusted directory. The path used to obtain it is not a trust anchor.

## Same-user result

A same-user replacement before the open is not detected. The handle refers to the substitute, and a child created from it is created on the substitute. A same-user replacement after the open does not redirect later creates. Those are different boundaries, and only the second one was contained.
