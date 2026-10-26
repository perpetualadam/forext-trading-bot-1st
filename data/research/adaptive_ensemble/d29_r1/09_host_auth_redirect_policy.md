# HOST, AUTHENTICATION, AND REDIRECT POLICY

Current authorisation: NONE. Naming a host here does not approve contact.

Candidate registry host: registry-1.docker.io. Candidate token host: auth.docker.io. Historical storage host, still not approved: production.cloudfront.docker.com.

A future client must use HTTPS on port 443, verify TLS certificates, and refuse every host that is absent from the approval allowlist. It must not read credential stores, invoke Docker credential helpers, use ambient registry authentication, discover environment proxies, or send a proxy request.

Redirects are not followed automatically. A bearer token is not forwarded to a storage host. Signed Location values and query strings are not stored or logged. An unexpected scheme, port, or unapproved host stops the stage. A failed approved host is not replaced with a different host.

Anonymous token retrieval requires its own future approval. No token is retrieved in D.29-R1. Tokens and signed URLs are not persisted.

If a response is HTTP 307 to an unapproved storage host, the future stage stops. The layer is not downloaded.
