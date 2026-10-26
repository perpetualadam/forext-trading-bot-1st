# FUTURE CLIENT SAFETY SPECIFICATION

This document does not implement a client.

Hosts, ports, and methods remain unauthorised. A future approval must name every hostname. The only proposed port is 443 and the only proposed method is GET. The repository identity is library/python. The only blob identifiers are the unique compressed digests in the D.29-R1 inventory. TLS certificate verification is required.

Anonymous authentication is a separate approval. Credential stores, Docker helpers, ambient authentication, and proxies are out of scope. Redirects are not automatic. Retries are prohibited. A registry token is not sent to storage and is not written to disk. Signed URLs are not retained.

Connection, inactivity, request, and stage limits are four different controls. Their numeric values are MISSING. A future approval must supply them before any socket is opened. Request and stage limits use a monotonic clock and do not reset on a new chunk or a new request.

Each blob body is capped at its declared size. Other bodies are capped at 1,048,576 bytes for comparison with the historical cap. The cumulative body ceiling is the reconciled total in the byte-budget artifact. The client streams bytes into SHA-256 and a counter. Content-Length is not trusted. A non-identity content encoding stops the stage. The retained object is the raw compressed body, not a decompressed tar.

Temporary files stay in the approved directory. Promotion happens only after size and digest match. Promotion is specified as a same-directory rename, not a second copy. Cleanup failure is fatal. Logs omit credentials, tokens, query strings, and signed locations.

An existing output file or a non-empty target directory stops the stage before the first request. Results are reproducible only when bound to these manifest digests. Evidence retained after success is the verified blob, its digest, size, and sanitised request record. D.29-R1 does not authorise extraction, execution, deployment, or trading.
