# FUTURE ARTIFACT SAFETY PLAN

Not implemented in D.28.

A later download stage would hash compressed bytes while streaming and stop on a digest mismatch. A later extract stage, separately approved, would verify uncompressed diff IDs before trusting a reconstructed root.

Extraction would stay inside an approved sandbox, reject path traversal, unsafe links, and device files, and bound expansion, file count, and disk use. Downloaded binaries would not be executed during static inspection. Signed storage URLs and credentials would not be written to evidence. An interrupted download would be discarded rather than reused.
