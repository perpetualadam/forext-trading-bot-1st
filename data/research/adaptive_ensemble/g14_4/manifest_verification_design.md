# G.14.4 manifest verification design

`tests/g14_4_verify.py` does not import the destination helper. It re-lists files and re-hashes bytes. A success value from any writer is not an input.

Hash integrity and source provenance are separate results. A matching SHA-256 does not prove an approved source. The synthetic checker reports `SYNTHETIC_NOT_AN_APPROVED_SOURCE` even when hashes match.

The checker rejects:

- a missing or extra file
- a non-wheel extra
- a hash or size mismatch
- a SHA-256 that is not 64 lowercase hex characters
- duplicate filenames and case-only collisions
- path traversal and absolute paths
- symlinks and reparse points
- wheel tags outside the linux/x86_64 CPython 3.12 set
- a source distribution
- duplicate or conflicting package versions
- a dependency name that is not in the set
- an index other than the synthetic fixture index
- an additional index, a direct URL, or a VCS requirement
- missing provenance
- an incomplete document or a wrong schema version
- credential-like metadata
- either sensitive backup filename
- `live_safety_state.json`
- a claim that resolution, acquisition, or verification is complete

The Gate A checker accepts only documents marked `SYNTHETIC_NOT_AN_APPROVED_LOCK`. It does not open wheel contents and does not execute them. Parsing files inside a wheel is a later permission.
