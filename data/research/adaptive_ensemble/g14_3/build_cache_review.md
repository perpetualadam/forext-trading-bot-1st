# G.14.3 build-cache review

G.14.2 reported 27.36 GB of build cache. That figure was not rechecked. The cache was not cleared or modified.

## Current proposal

The earlier build command leaves the default cache enabled.

## Risks

- A cached `pip install` layer can hide which versions were resolved.
- A cache hit can make a build succeed without contacting the index and without showing a fresh install.
- The cache key follows the Dockerfile instruction and its parent. An old layer built from the same base and the same unpinned requirements can be reused even though the index would now return different versions.
- BuildKit provenance for that cache was not inspected. `BUILDKIT_PROVENANCE_UNVERIFIED`.

## `--no-cache`

`--no-cache` improves auditability by forcing the `RUN` instructions to execute again. It increases network dependence while requirements are unpinned, and it does not by itself pin versions or hashes. It is not a reproducibility proof.

## Proposed later policy

Use the default cache only for experimental builds that are already labeled non-reproducible.

For the locked offline build, after a verified wheelhouse exists:

- `--no-cache` on that build
- `--no-index` and `--require-hashes`
- no cache mount in the candidate Dockerfile

A wheelhouse plus `--no-cache` still depends on the wheelhouse being the complete, hashed set. The cache must not be pruned to reach that state.
