# Wheel archive validation

`verify_wheelhouse` now calls `inspect_wheel_bytes` after the hash and size match. A non-ZIP payload is rejected. Inspection uses `zipfile` on an in-memory buffer. Members are not extracted to disk and are not imported.

The inspector rejects encrypted entries, absolute paths, parent traversal, duplicate names, case-colliding names, compression other than store or deflate, member counts, uncompressed sizes, and compression ratios above the configured limits. It requires `WHEEL`, `METADATA`, and `RECORD`, and it checks RECORD hashes and sizes. Metadata name, version, and tag must match the filename and the manifest.
