# OCI platform identity

A complete identity needs the operating system, architecture, variant when one applies, OS version, relevant OS features, the multi-platform index digest, the platform manifest digest, the image configuration digest, the layer digests, the registry origin, and the evidence that selected the platform.

These digest kinds are different:

- `MULTI_PLATFORM_INDEX_DIGEST` names an index that can point at more than one platform.
- `PLATFORM_MANIFEST_DIGEST` names one platform's manifest.
- `IMAGE_CONFIGURATION_DIGEST` names the image configuration.
- `LOCAL_IMAGE_ID` names a daemon-local image. It does not identify the registry index.

No digest of any of those kinds is present in the current Dockerfile. No digest was invented.
