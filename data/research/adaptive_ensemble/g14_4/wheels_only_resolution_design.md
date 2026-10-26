# G.14.4 wheels-only resolution design

This procedure was not executed. Resolution, acquisition, and verification are separate states. None of them is complete.

## Later procedure

1. Confirm the target is CPython 3.12 on linux/x86_64. The patch version, glibc, and SOABI are `UNKNOWN` and must be recorded before a lock is accepted.
2. Start from the nine direct requirements, including `uvicorn[standard]`.
3. Resolve the full transitive graph for that target. The graph is `UNKNOWN` now.
4. Evaluate environment markers for linux, CPython, 3.12. Do not use the Windows host result as the lock.
5. Accept only wheel tags in the still-unfinalized linux/x86_64 set. Reject other tags.
6. Reject `.tar.gz`, `.zip`, and other source distributions.
7. If a required package has no compatible wheel, stop with `COMPATIBLE_WHEEL_UNAVAILABLE`. Do not widen the index or relax a constraint.
8. Reject a direct URL requirement.
9. Reject a VCS requirement.
10. Reject a second index.
11. Reject a package name that is not in the resolved graph.
12. Reject a missing artifact.
13. Reject two versions of the same normalized name.
14. Reject metadata that disagrees with the filename or hash.
15. Reject a wheel filename that does not match the record.
16. Reject a partial graph.
17. Record the selected version only after resolution.
18. Record the wheel filename only after the artifact exists.
19. Record SHA-256 of the acquired bytes. Do not invent it.
20. Record provenance separately from the hash. A hash does not prove the source.

`--platform` alone does not settle marker evaluation or the ABI. If cross-platform `pip download` cannot show that markers were evaluated for the target, Gate B must stop and request a separate isolated linux/amd64 resolver. That environment is not created now.

## States

- `RESOLUTION_COMPLETE`: versions and the graph are known. Artifacts may still be absent.
- `ARTIFACT_ACQUISITION_COMPLETE`: the bytes are in the wheelhouse. They may still be unverified.
- `INDEPENDENT_ARTIFACT_VERIFICATION_COMPLETE`: a second checker has re-listed and re-hashed them.

Gate A claims none of these.
