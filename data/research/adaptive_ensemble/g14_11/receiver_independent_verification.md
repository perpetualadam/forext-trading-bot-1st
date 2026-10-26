# Receiver-side independent verification

The receiver verifies bytes it read from its own file handles. It does not trust the sender manifest, a filename, or a synthetic lock. It does not execute package code, does not install, and does not contact an index. Any mismatch is `FAILED_CLOSED`.

Existing helpers, not modified:

- `tests/g14_4_verify.py`: `parse_wheel_filename`, `inspect_wheel_bytes`, `_check_record`, `assert_dependency_graph`, `verify_member_bytes`, `accept_verified_lock`.
- `tests/g14_7_fs.py`: exclusive create, reparse attribute, volume serial, reserved names.
- `tests/g14_4_acquire.py`: `reject_member_name` for the two backup filenames and traversal.

## Required checks

- Approved package source: absent. Publication cannot reach `PROVENANCE_VERIFIED`.
- Approved artifact host: absent. Same.
- Filename: `parse_wheel_filename` and `_filename_problem`.
- Package name and version: taken from the wheel metadata the receiver parsed, then compared with the approved set. No set is approved.
- Size: equals the handle read-back length.
- SHA-256: computed by the receiver.
- Wheel-only: reject anything that is not a wheel.
- ZIP integrity and duplicate members: `inspect_wheel_bytes` / the archive reader. A duplicate member fails.
- Path traversal inside the archive: `_member_problem`.
- WHEEL, METADATA, and RECORD: `inspect_wheel_bytes` and `_check_record`.
- Dependency graph: `assert_dependency_graph`. Completeness against the production image remains `DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED` until the target profile exists. The receiver must not mark the graph verified while that blocker stands.
- PEP 508 markers: `_marker_result`. An unknown marker fails. It is not treated as true.
- Extras: only extras named in the approval. None are approved.
- Wheel tags: `_tag_problem` and `_wheel_tags` against the known tag set. The tag set is unknown, so `TARGET_COMPATIBILITY_VERIFIED` cannot be entered.
- No source distributions, source builds, installation, or code execution.
- No unapproved dependency, redirect, or source substitution. Redirects are not a verifier feature. They belong to a sender that does not exist. The receiver refuses provenance that includes an unapproved URL.
- No unexpected file in the receiver's own name list.

`accept_verified_lock` requires a wheelhouse path today. A future lock check must run on handle bytes, not by reopening a path the interactive user supplies. That change is described and was not made. A synthetic lock marked `SYNTHETIC_TEST_ONLY` is not production evidence.

## Gaps that stay open

Package source, registry digest, pip, SOABI, glibc, native tags, and a real lock. Verification design does not close them.
