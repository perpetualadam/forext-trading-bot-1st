# Protected Windows execution feasibility

Classification: `WINDOWS_BOUNDARY_FEASIBILITY_PLAUSIBLE_UNVERIFIED`

Verified isolation: no. No protected execution boundary was found. Same-user path substitution remains a demonstrated result from G.14.8.

This process is medium integrity, not elevated, and its Administrators group is deny-only. That describes the token that ran this review. It is not an acquisition sandbox.

## Mechanisms

### Restricted token

Not created. No test shows it stops another process of the same user from replacing a directory the user can write. G.14.8 level 1 is that replacement, without elevation. A restricted token was not shown to be a different principal. Claim not supported. Future test would require a separate approval. This stage did not launch one.

### Low-integrity process

Not created. The demonstrated substituter was able to rename a user directory. This review's token is medium. There is no evidence that running acquisition at low integrity stops a medium same-user writer. Host import by a medium process would still use a path that writer can replace. Claim not supported.

### AppContainer

Not created. No package identity, capability set, or directory ACL for an AppContainer was read. Unknown. Creating one is a future approval and was not done.

### Separate Windows user or service account

Not created. This token is not elevated, and elevation was not requested. Whether a new user would stop the current user depends on a DACL that was not written and not read. G.14.8 recorded same-user ACL control as `ACL_RESTRICTION_NOT_APPLICABLE` and the actual DACL bytes as `ACL_RESTRICTION_UNVERIFIED`. A different principal remains a design, not an observation. It would need elevation or an existing principal, plus ACL changes, which are prohibited here.

### Protected directory and ACL controls

No acquisition directory was created and no ACL was changed. The same-user attacker in G.14.8 could replace a directory in a location that user could write. An ACL the owner can rewrite is not a boundary against that owner. That is the prior finding, not a new ACL read.

### Mandatory integrity

Only this process's medium label was read. No label was applied to a directory. MIC was not tested as a write barrier.

### Handle inheritance and duplication

Not implemented. G.14.9 recorded that both require a trustworthy handle first, and the first open is still the race. Level 3 code: `open_directory` in `tests/g14_7_fs.py` still calls `CreateFileW` on the caller path. Level 4 design: G.14.9 Option A.

### Job objects and filesystem virtualization

No job object was created. No evidence shows a job object prevents path substitution. Filesystem virtualization was not observed. Both unknown.

### Restricted network

No Windows firewall rule, AppContainer capability, or WFP filter was read. Network restriction is unknown. This stage sent no request. The application flag `NETWORK_DISABLED` is level 3 code, not an OS boundary.

## Linux wheels and export

None of these Windows mechanisms identify glibc or manylinux tags. They do not become a Linux build of CPython 3.12 by being restricted. Export still lands on a host path unless a different receiving principal holds the import handle. No such principal exists. `ARTIFACT_IMPORT_TRUST_BOUNDARY_UNVERIFIED`.

## Privileges required for a stronger design

A separate user, a service, an ACL the current user cannot rewrite, or a feature change would need rights this process does not have, or a consent elevation that was not requested. That is an inference from the observed token, not a test that those rights are absent from the account. Account elevation ability remains unknown.

## Classification

`WINDOWS_BOUNDARY_FEASIBILITY_PLAUSIBLE_UNVERIFIED`

Same-user token, integrity, and owner-ACL ideas are not a candidate. They have a demonstrated hole or no test. A separate principal is not `BLOCKED` and not `SUPPORTED_BY_EXISTING_EVIDENCE`. It was not created. No Windows execution boundary is selected.
