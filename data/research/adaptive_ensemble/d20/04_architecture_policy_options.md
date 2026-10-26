# Architecture policy options

Option 1, `SINGLE_PLATFORM_AMD64`, matches the stated selection. It limits verification to one manifest, one ABI, one libc target, and one wheel set. It does not prove the future VPS is x86-64. Current approval status: the architecture is stated. The image digest, wheels, and VPS are not approved as verified facts.

Option 2, `DUAL_PLATFORM_AMD64_ARM64`, would require a separate manifest, Python patch, ABI, libc check, and wheel closure for each architecture, plus two candidate images and two runtime validations. A version that has an AMD64 wheel can still lack an ARM64 wheel. Current approval status: not approved. This stage does not choose it.

Option 3, `PORTABLE_SOURCE_TARGET_UNSELECTED`, waits for known hosting hardware. It does not remove architecture-specific verification once a host is chosen. Current approval status: not the stated decision, because `linux/amd64` is already selected.

The operative approved architecture remains Option 1 until the user explicitly confirms or rejects Option 2. Option 2 is documented for that decision only.
