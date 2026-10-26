# Controlled publication

Design only. The state machine was not implemented.

## States

`RECEIVER_UNINITIALISED`
`RECEIVER_AUTHENTICATED`
`DESTINATION_BOUND`
`TRANSFER_STARTED`
`TRANSFER_COMPLETE`
`BYTES_VERIFIED`
`WHEEL_METADATA_VERIFIED`
`DEPENDENCY_GRAPH_VERIFIED`
`TARGET_COMPATIBILITY_VERIFIED`
`PROVENANCE_VERIFIED`
`PUBLICATION_PREPARED`
`PUBLICATION_COMMITTED`
`FAILED_CLOSED`

Legal motion is forward one state, or to `FAILED_CLOSED` from any state. There is no skip. `PUBLICATION_COMMITTED` is not reachable while source approval, target profile, or the substitution test is missing. Those are missing now, so a faithful implementation would stop before `PROVENANCE_VERIFIED`.

## Rules

- No publication before every verification state.
- No publication of a partial transfer.
- No publication of a file that failed an approval check.
- No publication of a synthetic lock or `COMPLETE_SYNTHETIC` output.
- Publication is a record in the receiver directory: the handle identity, the receiver-computed hashes, and the SID. It is not a copy onto a path the interactive user names.
- Forbidden destinations, even if someone later asks: production mounts, operational-state mounts, shadow-state mounts, credential directories, the two backup filenames, the repository root, and the existing 63-file staging directory.

## The 15 publication questions

1. Atomicity: the commit is a single record written with `FILE_CREATE` on the receiver handle after all checks. A rename of a user-writable directory is not the commit. A rename can be atomic and still land on the attacker's directory.
2. Filesystem identity: volume serial and file index of the receiver directory handle, stored in the commit record, and checked again before the record is written.
3. Handle binding: the artifact bytes are re-read from the original file handles immediately before the commit. A path reopen is a failure.
4. Concurrent replacement: if the directory file id changes, `FAILED_CLOSED`. Post-open binding from G.14.8 is the tool. It does not prove the first open.
5. Same-user interference: if the substitution test was never passed, the machine stays at `RECEIVER_UNINITIALISED`.
6. Partial writes: `interrupted_write` does not advance past `TRANSFER_STARTED`.
7. Crash: a missing commit record means not published. Recovery does not invent the record.
8. Audit: state, reason, hashes, SIDs. No secrets. The audit file is itself created on the receiver handle.
9. Manifest binding: the commit names the receiver hashes, not the sender's.
10. Lock binding: a lock is published only as part of the commit, after provenance. No lock exists.
11. Post-publication mutation: the receiver keeps the handles and refuses a consumer read if the file id or hash changes. A consumer that copies bytes out has left the boundary.
12. Consumer authentication: consumer SID on a separate pipe, allowlisted.
13. Consumer authorisation: a recorded approval for that SID. None exists.
14. Receiving-side verification: the states above.
15. Consuming-side verification: the consumer hashes the bytes the receiver sends. It does not open the receiver directory by a path it was given.

`PUBLICATION_COMMITTED` was not reached. Classification of the live boundary: `ARTIFACT_PUBLICATION_BOUNDARY_UNVERIFIED`.
