# Dependency and build readiness

No download, install, or Docker command was run.

| Finding | Status | Evidence |
| --- | --- | --- |
| Direct requirements pinned | UNRESOLVED | `requirements.txt` has nine `>=` minimums and no `==` pins or hashes. |
| Transitive lock | UNRESOLVED | No lock file. G.14.3 and G.14.5 recorded the graph as incomplete. |
| Offline wheelhouse | UNRESOLVED | No wheelhouse exists. G.14.4 through G.14.8 designed and tested synthetic checks only. |
| Package-source approval | UNRESOLVED | `PACKAGE_SOURCE_APPROVAL_REQUIRED` remains from G.14.12. |
| Real HTTPS acquisition | UNRESOLVED | `REAL_HTTPS_SENDER_ABSENT`. |
| Target compatibility | UNRESOLVED | `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`. Python patch, SOABI, glibc, pip, and wheel tags were not established. |
| Base-image registry digest | UNRESOLVED | `BASE_IMAGE_DIGEST_UNVERIFIED`. Local id `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254` is not a registry digest. |
| Cold reproducible build | UNRESOLVED | No candidate image. Dockerfile lines 12-14 run `pip install --upgrade pip` and an unpinned `pip install -r requirements.txt`. |
| Receiving boundary | UNRESOLVED | G.14.12 classification `G14_12_NO_SUITABLE_EXISTING_PRINCIPAL_IDENTIFIED`. No receiver, directory, or pipe exists. |
| Current tree versus staging | RESOLVED_WITH_EVIDENCE | Working tree allowlist hashes match the 63-file staging manifest, and the staging directory was re-hashed to the same 63 files and 617279 bytes. That context is not an image. |
| Dockerfile allowlist repair | PARTIALLY_RESOLVED | The working-tree Dockerfile is the explicit COPY. It is not what built the historical image. |

`pip install` of a minimum version is not a pin. A package already present on this Windows machine is not an approved Linux wheel for `python:3.12-slim-bookworm`.

Build remains blocked. Repository-root context remains forbidden. The two sensitive backup filenames stay excluded from staging and must not be copied by a future broad context.
