# Acquisition-to-receiver protocol

Design only. No pipe, socket, or endpoint was created.

## Selected transport

Authenticated local bytes, receiver-opened, sender identified by SID.

The preferred shape is a named pipe whose server is the receiver process. The pipe name is not the trust anchor. Locality is not authentication. The receiver must read the client's token SID and accept only a configured sender SID. The sender must check the server SID and accept only the receiver SID. A pipe that skips either check is rejected by the contract.

Not selected:

- A shared folder, guest mount, or bind mount. That is a path the sender can race.
- A directory handle passed by the sender. The sender is the party who can substitute objects.
- An unauthenticated local socket. A local listener does not name its peer.
- Any network endpoint. No listener was created. Network approval is not granted.

Guest-to-host transfer can use the same byte protocol later. The guest is then only a sender. The host writer remains the R1 process.

## Checks

1. Sender authentication: client SID on the pipe equals the configured sender SID. Failure is `FAILED_CLOSED`.
2. Receiver authentication: server SID equals the receiver SID. The sender disconnects otherwise.
3. Principal separation: the two SIDs differ. Same-SID is not a receiver.
4. Replay: each transfer carries a receiver-generated nonce. A repeated nonce is rejected. The nonce is not a signature of package contents.
5. Framing: length-prefixed frames with a declared count and a declared total size before any file body.
6. Identity: each file has one basename, a decimal size, and a SHA-256 the sender claims. The receiver recomputes the hash from handle read-back.
7. Length: the frame length must equal the declared size and the bytes read back.
8. Total size: a maximum is fixed in the future approval. This stage does not invent a safe production limit. Exceeding the configured maximum fails closed.
9. File count: same rule. A count above the configured maximum fails closed.
10. Timeout: a stalled frame fails the transfer. No partial publication.
11. Interrupted transfer: `TRANSFER_STARTED` returns to `FAILED_CLOSED`. Bytes already written stay unpublished.
12. Duplicate names: second exact name fails.
13. Case-insensitive collisions: a different spelling with the same casefold fails, matching `_reject_collision` in `tests/g14_7_fs.py`.
14. Unicode: names must be NFC. A casefold or NFC collision with a different spelling fails. The current helper does not implement NFC. That is a future receiver requirement, not a claim about today's code.
15. Path traversal: a name that is not a single segment fails. Slashes, backslashes, and `..` fail.
16. Absolute paths: rejected as names. The sender cannot choose a destination path at all.
17. Alternate data streams: a colon in the name fails, as the helper's `path_traversal` check does.
18. Device names: the reserved-device check in `tests/g14_7_fs.py` applies before create.
19. Reparse points: a created handle with the reparse attribute fails.
20. Symlinks: not treated as proven. The reparse attribute is the fail-closed rule. Kernel symlink behaviour remains unexecuted.
21. Hard links: link count above 1 fails.
22. Unauthorized types: only `.whl` after the existing filename checks. No `.tar.gz`, no source tree, no lock presented as production.
23. Hash: receiver SHA-256 of handle bytes. Mismatch fails.
24. Provenance: source and artifact host must be on an approval that does not yet exist. Absent approval fails. `https://pypi.org/simple` and `files.pythonhosted.org` are not that approval.
25. Dependency graph: `assert_dependency_graph` on inspected wheels. Incomplete target profile fails the publication even if the graph function returns.
26. Target compatibility: unknown patch, SOABI, glibc, pip, and tags fail `TARGET_COMPATIBILITY_VERIFIED`.
27. Receiver authorisation: receipt approval recorded before `TRANSFER_STARTED`. Missing approval fails.
28. Audit: the receiver records SIDs, nonce, names, sizes, hashes, and the failure reason. No secret values.
29. Errors: any check moves to `FAILED_CLOSED`.
30. Fail closed: no fallback to `open_directory` on a sender path. No synthetic `COMPLETE_SYNTHETIC` result authorises this protocol.

## What the existing code already covers

`write_exclusive`, `verify_member_bytes`, `inspect_wheel_bytes`, and `assert_dependency_graph` are the verification tools to call on bytes. `DEFAULT_TRANSPORT` remains `NETWORK_DISABLED`. This protocol does not add a live sender. `tests/g14_7_transport.py` was not modified.
