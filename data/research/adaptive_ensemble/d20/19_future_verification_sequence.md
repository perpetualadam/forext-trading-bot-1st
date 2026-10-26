# Future verification sequence

These steps are proposals. None is authorised.

1. Explicit user approval or rejection of the dual-platform policy.
2. A separately approved read-only registry manifest read for the approved reference.
3. Separate identity checks for each approved platform. ARM64 is skipped unless step 1 approves it.
4. Python patch, ABI, distribution revision, and libc for each approved platform.
5. Wheel metadata for each approved architecture.
6. A controlled resolution and provenance review.
7. Offline artifact preparation.
8. Candidate image builds.
9. Isolated non-production runtime validation.
10. Production prerequisites, deployment authority, rollback, and operational safety.

A pass at one step does not start the next.
