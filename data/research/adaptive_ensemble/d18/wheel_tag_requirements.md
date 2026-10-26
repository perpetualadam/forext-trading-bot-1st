# Wheel tag requirements

Accepted tags need the interpreter implementation, Python version, ABI, operating system, architecture, libc family, and libc compatibility level. manylinux is the glibc wheel policy. musllinux applies to musl images and is the wrong policy for a Debian bot image if the glibc inference is later confirmed. Pure-Python wheels and `abi3` wheels follow different rules from version-specific native extensions.

No authoritative tag list was taken from the host interpreter. No platform tag was invented as a lock input.

An example shape such as `cp312-cp312-manylinux_*_<arch>` is `ILLUSTRATIVE_ONLY` and `NOT_TARGET_VERIFIED`. The architecture and manylinux version in that shape are not selected.
