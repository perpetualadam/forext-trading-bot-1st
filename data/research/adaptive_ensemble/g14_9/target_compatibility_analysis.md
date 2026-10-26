# Target compatibility across the three designs

Nothing here was measured on a Linux system. Docker was not used. The historical local image id was not refreshed and is not a registry digest.

## Fixed target, still incomplete

- Operating system: Linux.
- Architecture: x86_64 / AMD64.
- Implementation: CPython.
- Major.minor: 3.12.
- Image tag requested historically: `python:3.12-slim-bookworm`.
- Historical local image id: `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`.
- Python patch: unknown.
- SOABI: unknown.
- glibc: unknown.
- Pip: unknown.
- Native wheel tags: unknown.
- Registry manifest digest: unknown.

Preserved classifications:

- `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`
- `BASE_IMAGE_DIGEST_UNVERIFIED`
- `PIP_TOOLCHAIN_VERSION_UNVERIFIED`
- `DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED`

## What each design could eventually do

These are capabilities a later, separately approved environment might have. None was demonstrated.

| Question | Option A | Option B | Option C |
| --- | --- | --- | --- |
| Identify the Python patch | No. The workflow would still be on Windows. | Only inside a Linux guest that is the production image or a proven match. The guest is not selected. | No. Same host as today. |
| Identify SOABI | No. | Same limit as the patch. | No. |
| Identify glibc | No. | Same limit. | No. |
| Identify wheel tags | No. Tags would be guessed from an incomplete profile. | Only after the guest reports them. Unknown now. | No. |
| Identify pip | No. | Only if a later stage is allowed to query it. Not allowed now. | No. |
| Verify base-image identity | No. A handle on Windows does not name a registry manifest. | Only with a registry digest and a guest identity. Both unknown. Docker inspection is not approved. | No. |
| Keep an immutable target definition | The definition can be written down. It cannot be checked from Windows. | Same, until a guest is bound to a digest. | Same as A. |
| Resolve a complete graph | No. The graph depends on the target markers and tags. | No, until the profile is complete and the index is approved. | No. |
| Select native wheels | Not without tags. | Not without tags. | Not without tags. |
| Reject incompatible wheels | The current synthetic checks can reject a wheel that declares an incompatible tag only when the required tags are known. They are not known. | Same. | Same. |
| Avoid source builds | The policy can forbid them. A Windows helper cannot prove a future Linux installer would obey that. | A guest could be required to install only wheels, later. Not set up. | Policy only. |
| Avoid build hooks | Same. No hook was executed in this stage. | Same. | Same. |
| Deterministic offline install | Not evidenced. There is no lock and no wheelhouse. | A guest does not create those by existing as an idea. | No. |

Option B is the only design in which a Linux observation could later happen without using the production container. That is not a reason to start a guest. The image digest and the daemon behaviour are unverified, so a guest started from the tag `python:3.12-slim-bookworm` would not yet be the production target.

No design may claim the compatibility profile is complete.
