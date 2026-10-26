# Selection and verification

These states are separate.

- Selected platform: the user has explicitly chosen an OCI platform. Status: not selected.
- Verified platform: independent evidence establishes the target properties. Status: not verified.
- Confirmed registry: the user has explicitly approved the registry and repository. Status: not confirmed.
- Verified image: a digest and provenance establish image identity. Status: not verified.
- Lock-eligible target: Python, OS, architecture, ABI, and artifact inputs are sufficiently established. Status: not eligible.
- Deployment-ready target: build, runtime, safety, authority, and rollback conditions are satisfied. Status: not ready.

An assistant note, a historical image, a Dockerfile tag, a completed audit, and the instruction to run D.19 do not move any of these states.
