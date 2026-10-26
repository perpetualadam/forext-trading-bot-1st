# Artifact export and import feasibility

Result: `ARTIFACT_IMPORT_TRUST_BOUNDARY_UNVERIFIED`

No export channel was created or tested. Guest isolation, even if it were later shown, would not make a host `CreateFileW` on a user-writable path safe. G.14.8 level 1: that open binds to a directory substituted by the same user.

## Current evidence against the checklist

1. Acquisition-side verification exists only as the handle-read wheel checks in the research helper. They were not run inside a VM, WSL distribution, or new container.
2. Lock verification for a real lock does not exist. No lock was created.
3. Guest filesystem ownership: no guest.
4. Guest mutability: no guest.
5. Guest artifact replacement: no guest.
6. Export mechanism: none identified that avoids a host path open.
7. Export channel authentication: none.
8. Export destination ownership: not read.
9. Host destination trust: not established. The 63-file staging tree is not a wheel destination.
10. Host path substitution: demonstrated before the open.
11. Host reparse points: a junction was rejected when it was the opened object. Other tags were not enumerated.
12. Host symlinks: not executed, errno 22 in G.14.8.
13. Host junctions: tested in G.14.8, not re-run here.
14. Host-side hash verification: possible on bytes actually read. A hash does not prove the directory was intended.
15. Host-side wheel metadata verification: the existing verifier can do this on bytes it has. It was not pointed at an imported tree.
16. Dependency-graph verification: still incomplete for the production target.
17. Lock verification: no real lock.
18. Post-verification replacement: contained only while the verified handle is the one used for the later read.
19. Atomic publication: a rename of a user-writable directory is not atomic against that user.
20. Build-context creation: not done. The staging context stays the 63-file tree.
21. Build-context integrity: staging reverified. That is not an import of wheels.
22. Credential exclusion: backup files were not read. No environment values were stored.
23. Unexpected-file exclusion: staging verifier would reject extras. No new tree was built.
24. Cleanup: no new guest or directory to recover. Historical probe directories were not deleted.
25. Evidence preservation: G.14.2 through G.14.9 files were not modified.

## Future designs that were not tested

A protected receiving directory, an authenticated transfer endpoint, handle-bound receiving, a separate import principal, a read-only artifact channel, and a split between verification and publication are design options only. Each needs a receiving anchor this user cannot replace before the receiving open. No such anchor was observed. Until one is shown, the import boundary stays unverified.

The G.14.7 verifier can be the acquisition-side checker later. It cannot stand in for the receiving open.
