# Legacy consumed evidence preserved through read-isolation correction

Session 36c7d101ab3f4fe3ae3889408735bdc7 remains at its original protected archive paths. No grant, journal, claim, result or consumed evidence was moved, reset, deleted or overwritten. Before/after hashes, sizes and modification times match the existing read-only snapshot.

- journal.json: e81d6cb96b76a114ef6046ff28abca425af4416c2f8f2e6e3ea81ec31ea2fdc9; 129 bytes; mtime_ns 1793207760544294700.
- grant.claimed.json: b4a524d24f1b5e8735cc26c8adfecd37575d0bfe4f63ecf6d491292993b5e6d4; 523 bytes; mtime_ns 1793207760150680600.
- worker.claimed.json: d605487ce65931b9ddb80b033fa1763e6485199650182b6c841e6226746c950c; 149 bytes; mtime_ns 1793207760519550800.

The journal still records REQUEST_ATTEMPTED and one attempt. There is no saved historical response. The established OUTCOME_UNKNOWN assessment is unchanged: whether OANDA received HTTP remains unknown. No response was fabricated and ambiguity was not reclassified as failure. The existing timeout review is unchanged.

The correction removes these legacy authority paths from a namespaced worker's read allowlist. Negative tests use disposable synthetic lookalikes, not real legacy-record open attempts. Real legacy hashes are checked separately read-only by the review process, never by an acquisition worker. Explicit legacy operation retains its own scope while excluding child namespaces.

The non-authorising c202998c655f4af7b066a31f9636aed6 directory and superseded preparatory directories are also preserved unchanged, with no LIVE grant. The new source makes the current proposal stale; no replacement grant or session was created. Operational sources, R.56 controls/marker metadata, frozen strategies, local data and scheduler work remain preserved.
