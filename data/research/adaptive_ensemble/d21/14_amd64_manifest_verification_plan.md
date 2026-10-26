# AMD64 manifest verification

This plan applies to `linux/amd64` only. It was not executed.

A later approved stage records the descriptor digest, size, and media type from the index, then retrieves that manifest. It preserves the exact bytes, computes SHA-256, and compares the result with the descriptor. It validates the schema, records the configuration descriptor and the layer descriptors, and checks that the manifest stays associated with `linux/amd64`. A digest mismatch, a size mismatch, or an unsupported media type stops the stage.

The manifest retrieval is a separate approval from the index read. Configuration blobs and layers are not part of this retrieval.
