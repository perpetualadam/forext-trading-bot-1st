# Receiver-to-build contract

Classification: `RECEIVER_TO_BUILD_BOUNDARY_UNVERIFIED`

No build context was created. The 63-file staging directory is not a wheelhouse and must not gain one. Candidate packaging stays a separate approval. No image is built. The historical Docker daemon is not a consumer.

## Consumer

The only consumer the design allows is a process whose token SID is on the receiver's allowlist and that reads bytes from the receiver over the authenticated pipe. It does not receive a filesystem path.

A process of the interactive user may be that consumer only for bytes, and those bytes are then untrusted the moment the user writes them to a directory the user controls. The trust claim ends at the receiver's re-read. A Docker context directory built by this user is a new tree. It is not `PUBLICATION_COMMITTED`.

The production container is not a consumer. The existing staging tree is not a consumer.

## Required behaviour

- Authenticate the receiver by server SID before reading.
- Identify the published object by the commit record's file id and hashes, checked by the receiver at send time. The consumer never opens that object by path.
- Path substitution against the consumer's later private copy is outside the claim. The consumer must not describe that copy as the published object.
- Hash the received bytes and compare them with the receiver's commit. Mismatch fails.
- Re-run wheel metadata checks on those bytes. Do not trust the receiver's word alone.
- Re-check the lock against those hashes. No lock exists.
- Re-check the dependency graph. Completeness stays unverified while the target profile is incomplete.
- Re-check wheel tags against the same unknown tag set. Unknown tags fail.
- Hold the received bytes in the consumer process until its own checks finish. A path drop between check and use is a new race and is not success.
- Reject unexpected names, case collisions, and non-wheels.
- Reject `main example .env backup.txt` and `# Copy to .env and fill in. docker.txt` by filename, without reading them.
- Reject credential names, operational-state names, research trees, and any path that is another project, including Consensus Forecast.
- Do not talk to the production Docker daemon. A later candidate build is a different approval and still has `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED` and `BASE_IMAGE_DIGEST_UNVERIFIED`.

## Staging

G.14.1's 63 files stay as they are. Wheels are not added beside them. A future candidate context is a new tree under its own approval, filled with bytes from this protocol, and only after publication is actually implemented and tested.

## Future tests

The adversarial plan covers consumer substitution, unauthorised consumers, and production mounts. None of those tests was run.
