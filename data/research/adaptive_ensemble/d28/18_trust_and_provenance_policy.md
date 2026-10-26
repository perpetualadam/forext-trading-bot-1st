# TRUST AND PROVENANCE POLICY

Level 1 is OCI descriptors and config declarations. Level 2 is digest-verified compressed layer bytes. Level 3 is a verified reconstructed filesystem and static inspection. Level 4 is an isolated runtime measurement bound to a digest. Level 5 is a final bot image measurement. Level 6 is the target VPS.

A matching digest does not authenticate the publisher. A mutable tag can move away from this snapshot. Compressed digests and uncompressed diff IDs answer different questions. Static file inspection does not prove a process starts. A base-image measurement does not describe the final bot image or the VPS.

No signature or attestation was verified. D.28 adds no chain-of-custody bytes beyond hashes of files already on disk.
