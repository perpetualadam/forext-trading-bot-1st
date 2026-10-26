# Receiver-to-build trust

Classification: `RECEIVER_TO_BUILD_BOUNDARY_UNVERIFIED`.

No consumer was created. No build context was created. The 63-file staging directory was only re-read and was not modified. It is not a wheelhouse.

## Consumer

The consumer is a process whose SID is on the receiver allowlist and whose program and configuration sit on a chain that meets the same ancestor contract. That SID is not identified. The interactive user may receive bytes only as an untrusted copy. That copy is not the published object.

The consumer checks the server SID before payload bytes, hashes the payload, re-runs the wheel checks, and compares provenance, lock identity, and target profile with the commit fields. Unknown tags fail. A synthetic lock fails. Unexpected names fail. The two backup filenames and `.env` names fail unread.

There is no consumer path open, so there is no consumer ancestor to measure. When a consumer directory is later proposed, it needs the same ownership and DACL rules. Until then the anchor is unspecified in the filesystem and specified only as "not a user-writable path".

Handle lifetime is the receiver's. The consumer does not hold the directory handle.

Docker is not a consumer. The historical daemon was not contacted. The socket is out of the allowlist. Production mounts, operational state, shadow state, credentials, and the repository-root context are out. A future candidate context needs its own approval and must not be the existing staging tree.

Failure handling is `FAILED_CLOSED` with no image build and no staging edit. A mismatch does not fall back to opening a directory.
