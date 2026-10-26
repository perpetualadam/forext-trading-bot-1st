# Future approval stage plan

These stages are not authorised. Each one needs its own approval. D.16 does not start any of them.

## A. Dependency locking and provenance

Record exact direct and transitive versions and hashes for a named Python version and platform. Network resolution may be required. Do not install into the environment used by production, do not build an image, and do not deploy.

## B. Offline artifact acquisition

Download only the locked artifacts into a nonproduction wheelhouse and verify hashes. Network is required. Docker, credentials, and production access are not.

## C. Base-image identity

Record the registry digest for the intended base image without pulling it into a production daemon. Network may be required. Do not tag or run the image.

## D. Build-context hash manifest

Hash the current Dockerfile copy set and the dirty-tree inventory. This can be offline. Do not archive a deployment context and do not copy files to a receiver.

## E. Runtime profile

Specify architecture, user, health check, limits, and the Python version that matches the locked wheels. Do not inspect production to fill gaps.

## F. Trusted receiver

Design and, only if separately approved, implement an independent receiver. Privilege changes require their own approval. Do not stage a candidate.

## G. Candidate build and attestation

Build only after A–F. Docker is required. Production mounts, credentials, and deployment are prohibited.

## H. Production compatibility inspection

Read-only inspection of container identity, schema, and state mounts. Production access is required. No restart, no migration, no broker call.

## I. Rollback target

Prove a known-good image is available and compatible. Do not use the historical unsafe image. Do not roll back production.

## J. Deployment rehearsal

Exercise the candidate on nonproduction data. No live orders and no production write.

## K. Controlled deployment

Not reachable until A–J pass and rollback is verified. This plan does not authorise K.
