# Provenance limitations

- Digest equality verifies byte identity against the previously trusted descriptors.
- Digest equality does not independently establish publisher authenticity.
- The mutable tag may later resolve to different content.
- The AMD64 and ARM64 images have distinct platform manifests and distinct config digests.
- Image signatures and attestations remain unverified.
- No image layers were retrieved.
- No runtime execution occurred.
- No native dependencies were resolved.
- Verified config blobs are not a production rollback artifact.
