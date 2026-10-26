# G.14.8 handle-bound operations

The synthetic workflow still creates artifacts, reads them back, verifies those bytes, and writes `synthetic-lock.json` through the child directory handle. `verify_member_bytes` does not reopen the directory. G.14.7's end-to-end run passed again after the filesystem helper change and finished in `COMPLETE_SYNTHETIC` with `SYNTHETIC_TEST_ONLY`.

No path-based fallback was added. `open`, `shutil`, and `verify_wheelhouse` are not on the workflow completion path. The older path-based `verify_wheelhouse` remains for earlier tests.

The bound operations are only as trustworthy as the parent handle. A pre-open substitution makes the child handle bound to the substitute, and the workflow can still complete. Handle-relative operations do not repair that.
