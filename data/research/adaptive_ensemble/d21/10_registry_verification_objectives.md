# Registry verification objectives

This procedure is a design. No objective is complete.

The proposed registry is `docker.io`. The proposed repository is `library/python`. The proposed tag is `3.12-slim-bookworm`.

1. Establish the registry endpoint identity.
2. Retrieve the OCI index or Docker manifest list.
3. Preserve the exact response bytes.
4. Compute the digest of those raw bytes.
5. Record the digest reported by the registry.
6. Compare the computed digest with the reported digest.
7. Enumerate platform descriptors.
8. Identify exactly one `linux/amd64` descriptor.
9. Identify exactly one `linux/arm64` descriptor.
10. Preserve each selected platform manifest digest.
11. Verify descriptor media types.
12. Record manifest sizes.
13. Detect ambiguous or duplicate descriptors.
14. Record the response date and the limits of what the response proves.
15. Produce the audit trail defined by the evidence schema.

No request was sent. No digest was calculated from registry bytes.
