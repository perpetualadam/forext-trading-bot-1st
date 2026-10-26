# Architecture decision

Decision: `R1_DEDICATED_WINDOWS_PRINCIPAL_DESIGN_PREFERRED`

This is a design preference. It is not an implementation approval. It is not a verified boundary. The account was not created.

## Why R1

The G.14.8 failure is a path open by a token that can also replace the path. The receiver must be a different SID, must open a directory that SID created, and must accept bytes rather than a path or a handle from the sender. A second process of the same user does not do that. A service does not do that unless it is that other SID and its binary is equally protected. A guest does not do that if export is a host path.

R2 is deferred. It adds a service binary and SCM without new evidence that a service is safer.

R3 is rejected as the receiver. G.14.10 did not verify VM, WSL, or container isolation. A shared folder would restore the race. A guest may later be a sender.

R4 path-only designs are rejected. They are the demonstrated failure.

## Contract the preference actually states

- Principal: a non-administrator local account that is not the interactive user.
- Anchor: a directory that account creates and opens. The handle is the anchor. The sender's path is not.
- Same-user resistance: required as a test result before any artifact is accepted. Not yet a result.
- Acquisition boundary: SID-authenticated byte pipe. No shared folder.
- Publication boundary: commit record on that handle. Not a rename into a user directory.
- Build boundary: consumer gets bytes after its own checks. A path the interactive user opens is not the published object.
- Privileges: creating the account needs a future elevated approval. Running the receiver must not be administrator. This process is not elevated.
- Assumptions that are not evidence: a medium-integrity interactive user cannot rewrite the receiver DACL; this account might still elevate later because Administrators is deny-only on the current token; administrators are not defended against.

## Why implementation is blocked

The preference meets the design checklist and still must not be built yet. There is no principal, no directory, no ACL measurement, and no failed substitution test. Building it now would present an unverified account as a boundary. `RECEIVING_PRINCIPAL_UNVERIFIED` and `RECEIVING_DIRECTORY_TRUST_ANCHOR_UNVERIFIED` stay in force.

Gate B, network, downloads, Docker, WSL, VM, and Windows security changes are not granted.
