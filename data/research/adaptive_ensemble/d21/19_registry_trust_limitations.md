# Registry trust limits

TLS verification is required for a future read. It shows that the connection matched a presented certificate. It does not show that the publisher is the party the project intends, and it does not show that the bytes are safe to run.

A matching digest shows that the retrieved bytes correspond to that digest. It does not show that the content is safe. A mutable tag can point at different bytes later. A multi-platform index can point at different images for `linux/amd64` and `linux/arm64`. Registry metadata does not review application safety. Signatures and attestations need a separate provenance check. A manifest is not a rollback artifact.

An image is not trusted merely because a digest matches.
