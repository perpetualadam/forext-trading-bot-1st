# Wheel tag requirements

These distinctions are general packaging knowledge. They are not verified project facts.

An artifact name can carry an interpreter tag, an ABI tag, and a platform tag. A `py3-none-any` wheel is pure Python. A CPython wheel names `cp312` and an ABI such as `cp312`. Linux glibc wheels use `manylinux` tags. Alpine uses `musllinux`. Those tags are not interchangeable. An `x86_64` wheel does not satisfy `aarch64`.

`Requires-Python` and environment markers are evaluated by a resolver for one target. A complete Python 3.12 set does not cover Python 3.13. A complete set for one architecture does not cover another.

Project-local evidence stops at the requirement text and the image tag. Exact tags for numpy, pandas, and psycopg2-binary are future verification. No wheel file is in the project, so no tag was read from an artifact.
