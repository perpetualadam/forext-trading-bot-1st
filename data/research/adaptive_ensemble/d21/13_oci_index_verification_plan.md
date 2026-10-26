# OCI index verification

A future stage preserves the raw index bytes, hashes those bytes, checks the media type, checks that the JSON schema is an index or manifest list, and inventories every descriptor. Each descriptor needs a digest, a size, an operating system, an architecture, and a variant when one is present.

The check looks for exactly one `linux/amd64` runtime descriptor and exactly one `linux/arm64` runtime descriptor. Duplicate matches are ambiguous and stop the stage. A missing match stops the stage. Extra platforms are recorded and are not selected. Attestations and other non-runtime descriptors are recorded separately and are not treated as the runtime image.

The index digest and a platform manifest digest are different values. A local image configuration ID is a third value. No digest was invented.
