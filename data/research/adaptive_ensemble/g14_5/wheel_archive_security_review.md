# Wheel archive security

`tests/g14_4_verify.py` reads wheelhouse bytes only to compute SHA-256 and compare length. It does not open the bytes as a ZIP archive.

It therefore does not reject a malformed archive, encrypted entries, archive path traversal, duplicate members, unsupported compression, excessive decompressed size, a high compression ratio, missing `WHEEL`, missing `METADATA`, or a missing `RECORD`.

A G.14.5 test feeds non-zip bytes under a valid wheel filename. The verifier returns `hash_integrity: PASS`. That result is hash verification only. It is not archive, metadata, dependency-graph, or provenance verification.

No archive member was extracted and no package code was imported.
