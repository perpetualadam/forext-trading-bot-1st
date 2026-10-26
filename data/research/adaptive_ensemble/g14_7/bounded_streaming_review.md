# G.14.7 bounded streaming

Streaming is implemented only for `SyntheticResponse` values. There is no socket read.

## Enforcement

- A chunk larger than 65536 bytes fails with `oversized_response` and is not appended.
- A declared artifact size, content length, or accumulated body above 1048576 bytes fails with `oversized_response`.
- The running total of accepted wheel bodies above 4194304 bytes fails with `oversized_response`.
- `headers_size` above 8192 fails with `oversized_headers`.
- `elapsed_ms` above 5000 fails with `timeout` before the body is accepted. The test does not sleep.
- Status 503 may be exchanged again. The third retryable response fails with `retry_exhausted`.
- Any other non-200, non-redirect status fails with `unexpected_status`.
- Redirects are not followed by the transport. Each next URL is authorized first. More than two redirects fail with `excessive_redirects`.
- `complete` false fails with `interrupted_stream` and does not write a file.
- A content length larger than the bytes received fails with `truncated_response`.
- A content length smaller than the bytes received fails with `conflicting_size`.
- An empty body fails with `truncated_response`.
- The index body must be `application/vnd.g14-synthetic-index+json`. A wheel body must be `application/octet-stream`. Anything else fails with `unexpected_content_type`.
- The index body must be the canonical JSON of the in-memory fixture. A different body fails with `index_mismatch`.
- The wheel SHA-256 and size are checked against the fixture before the file is written.

A failed stream does not move the workflow to `COMPLETE_SYNTHETIC`. Partial files created by a later filesystem failure are left in place. The workflow does not delete them and does not write `synthetic-lock.json` after a failed verification.

## Gap

These limits are enforced on the injected response object. They do not demonstrate that a future socket reader would apply the same limits. That behavior is `LIVE_NETWORK_BEHAVIOR_UNVERIFIED`.
