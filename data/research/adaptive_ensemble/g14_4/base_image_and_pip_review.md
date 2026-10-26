# G.14.4 base image and pip review

Historical local image ID, not rechecked in this stage:

`sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`

Tag: `python:3.12-slim-bookworm`

Registry manifest digest: `UNKNOWN`

Base-image pip version: `UNKNOWN`

Classifications that remain:

- `BASE_IMAGE_DIGEST_UNVERIFIED`
- `PIP_TOOLCHAIN_VERSION_UNVERIFIED`

No Docker command was run. No registry was queried. No digest was invented.

A later lock must record the pip version and the resolver identity that produced it. Without that toolchain record, the lock is not reproducible even if versions are later filled in.

A future image inspection, under its own approval, would need to read the Python patch, SOABI, glibc, and pip version from the image without starting the forex application. That inspection is not part of Gate A.
