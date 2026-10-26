# G.14.3 dependency locking options

No lockfile was generated. No package was downloaded. Transitive versions remain `UNKNOWN`.

The direct requirements are nine `>=` constraints with no upper bound, no exact pin, and no hashes. The Dockerfile uses `--prefer-binary`, which still allows a source distribution when a matching wheel is absent.

## A. Exact-version requirements with hashes

- Reproducibility: high for the named files, incomplete unless every transitive distribution is listed.
- Auditability: high once hashes exist. They do not exist now.
- Network: the final install can be offline only with a local artifact store.
- Index trust: moved from install time to the earlier resolution.
- Platform and Python: hashes must be chosen for CPython 3.12, linux/amd64, matching the recorded base image.
- Native extensions and hooks: reduced if only wheels are allowed.
- Current Dockerfile: it has no `--require-hashes` and upgrades pip. A production edit is not proposed.
- New files and approval: a hashed requirements file, then Permission D. Not created here.

## B. Generated lockfile with the full transitive graph

- Reproducibility: high if the lock is platform-specific and hashed.
- Auditability: the graph can be reviewed. Inventing it from the nine direct lines would be a false lock.
- Network: resolution needs an index. That is a future permission, not this stage.
- Status: `UNKNOWN`. No lock was produced.

## C. Verified wheelhouse and offline installation

- Reproducibility: high for the final image if the wheelhouse is complete, hashed, and installed with `--no-index --only-binary=:all: --require-hashes`.
- Auditability: an independent pass can reject extra files, missing hashes, and changed hashes.
- Network: none during final assembly. Acquisition remains a separate earlier permission.
- Status: no wheelhouse exists.

## D. Controlled online resolution, then hash and freeze

- This is the evidence step that A, B, and C require.
- It contacts an index, selects exact versions for cp312/manylinux/x86_64, and records filenames and SHA-256.
- It must not install into the production environment and must not build the image.
- Package-index trust and installation hooks during any resolver-side build remain explicit risks.
- Status: not executed. Versions and hashes stay `UNKNOWN`.

## E. Immutable prebuilt dependency layer or base image

- A digest-pinned base would freeze the operating system and the base pip, not the application requirements.
- No registry manifest digest is known. The recorded value repeats the local image ID.
- This does not replace a dependency lock.

## Recommended sequence

Use D, then B and A together, then C. Keep that sequence out of the production Dockerfile. Put the lock, wheelhouse, and install flags in a future candidate-specific Dockerfile after the hashes exist.

That sequence is a design. It is not an implemented lock, and a reproducible image cannot be built from the current evidence.
