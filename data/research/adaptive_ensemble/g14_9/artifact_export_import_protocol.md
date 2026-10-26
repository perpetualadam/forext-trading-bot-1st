# Artifact export and import protocol

Design only. This protocol was not implemented. No wheelhouse, lockfile, or export directory was created.

A SHA-256 match proves that the bytes hashed are the bytes named in the digest. It does not prove that the package index was approved, that the directory was the intended directory, or that the bytes are the right build for the production image. A lockfile does not prove those things either. A secure-looking guest does not make a host path open secure.

## Two sides

### Acquisition-side verification

Minimum evidence the producer must be able to show, from handles it still holds:

- Each artifact name passed the single-segment checks: no slash, backslash, colon, traversal, trailing dot or space, control character, or reserved device stem.
- Each artifact was created with `FILE_CREATE` on the child directory handle, not opened by path afterwards.
- The handle's reparse attribute was clear, the volume serial matched the parent handle, and the link count was 1 at create time.
- The bytes were read back from that file handle.
- SHA-256 and size were computed from those bytes.
- Wheel archive and metadata checks ran on those bytes, using the existing verifier rather than a path scan.
- The dependency set is exactly the selected set. Completeness against the production image is a separate, still unverified claim.
- The lock document is marked synthetic until a real download is separately approved. A real lock would have to name the approved source. No such source exists.
- The producer records its boundary identity. Under Option A that identity is only the file id of the opened object. Under Option C it is a declaration. Under Option B it would have to name the isolation boundary, which is not selected.

The producer manifest is a claim. It is not an input the receiver trusts.

### Receiving-side independent verification

The receiver:

- Reads the bytes through its own handles.
- Computes its own SHA-256, size, and wheel checks.
- Builds its own file list.
- Compares that list to the producer claim.
- Fails closed on any mismatch, extra file, missing file, case-folded collision, duplicate name, reparse point, symlink, hard link, or unexpected volume.
- Does not execute wheel contents, setup hooks, or PEP 517 backends.
- Treats a match as integrity of the transfer, not as source approval and not as proof the producer opened the intended directory.

If the receiver's first open is `CreateFileW` on a path this user can replace, the receiver has repeated G.14.8. The protocol does not have a receiving-side anchor today. That gap is why no option is ready.

## Checklist

1. Names are single path segments and pass the reserved-name rules already in `tests/g14_7_fs.py`.
2. Sizes are the sizes read from the file handles, not sizes declared by an index.
3. SHA-256 is computed by both sides from bytes each side read.
4. Wheel archive integrity uses the existing archive checks on those bytes.
5. Wheel metadata integrity uses the existing metadata checks. Metadata is untrusted until those checks pass.
6. Dependency-graph completeness remains `DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED` until the production target is known.
7. Lockfile completeness is the selected set plus hashes and sources. An incomplete target profile means the lock cannot yet be complete.
8. Lockfile provenance must name an approved source. None is approved. A synthetic marker is not provenance.
9. Source approval is a separate decision. This protocol does not grant it.
10. File ownership was not read in G.14.8. Ownership would be recorded only if a later stage can query it without changing ACLs. It is not a same-user boundary by itself.
11. Symlinks are rejected if the object carries the reparse attribute. Kernel symlink behaviour was not executed.
12. Other reparse points are rejected when the attribute is set. Tags were not enumerated.
13. Hard links with link count above 1 are rejected at create in the current helper. A later replacement by a hard link is a new open and must be rejected again by the receiver.
14. Unexpected files fail the receiver's own inventory.
15. Duplicate filenames fail.
16. Case-insensitive collisions fail. The current helper raises `case_collision` before the second create when the spelling differs.
17. A short read fails as a partial transfer. The partial file is not published.
18. An interrupted transfer is not retried into a published directory.
19. Concurrent replacement before the receiver's open is the G.14.8 finding and fails this protocol closed only when the receiver can detect it. The current path open cannot.
20. Modification after verification is prevented only while the consumer uses the verified handle or a boundary the modifier cannot write.
21. Atomic publication by renaming a user-writable directory is not atomic against the same user. It is not the publication step.
22. Destination trust is the same problem as the original parent. The 63-file staging tree is not a destination for wheels.
23. Import verification is the receiving-side list above.
24. An incomplete transfer is not renamed into place and is not deleted by a broad cleanup. Leave it and fail.
25. Cleanup does not remove the G.14.1 staging directory, historical probe directories, production files, or a directory whose identity was not established.

## What each option adds

Option A can keep producer and consumer on one retained handle, so there is no export. The moment a later tool reopens the directory by path, the race returns. The launcher does not supply the missing pre-open anchor.

Option B adds a real export. Guest verification plus a host path open is not two-sided verification. The host side needs a read the same user cannot swap. That read was not identified.

Option C publishes on a path it has declared trusted. The declaration includes the attacker who can swap the publication. The two-sided hash still does not notice a swap that happens before both sides open the substitute, if both sides are the same user and both open the same replaced path.
