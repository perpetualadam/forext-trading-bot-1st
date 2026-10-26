# Future network boundary

D.23 authorises no network access. The D.22-R1 authorisation is closed and does not include config blobs. A config blob is a registry blob. Retrieval requires a new approval.

## Checklist for that future approval

- Registry authority: proposed `registry-1.docker.io`, HTTPS port 443 only.
- Token authority, only if a matching bearer challenge arrives: proposed `auth.docker.io`.
- Repository: `library/python`.
- AMD64 config digest: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`.
- ARM64 config digest: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`.
- Exact blob paths:
  - `/v2/library/python/blobs/sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`
  - `/v2/library/python/blobs/sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`
- Authentication policy: anonymous bearer only. No personal credentials, no Docker credential helper, no Basic authentication.
- Token query, if required: `service=registry.docker.io` and `scope=repository:library/python:pull`. No extra parameters.
- Allowed method: GET.
- Allowed request count: 4 maximum.
  1. GET the AMD64 config blob with no Authorization header.
  2. GET the anonymous token only if that response is 401 and the challenge matches.
  3. Repeat the AMD64 blob GET with the anonymous token only if the token was obtained.
  4. GET the ARM64 config blob, with the anonymous token only if one was obtained.
- If the first blob returns 200, do not request a token.
- If the second blob returns 401 after the first succeeded without a token, stop. Do not add another token request.
- Timeout: 30 seconds per request.
- Maximum response size: 1 MiB transport cap, with acceptance only at the exact descriptor size.
- TLS verification: certificate and hostname checks required.
- Redirect handling: reject 3xx and do not follow Location.
- Proxy handling: stop if a proxy is required or cannot be excluded.
- Response preservation: exact blob bytes in a new evidence directory. Do not write them into D.22, D.22-R1, or D.23.
- Digest validation: independent SHA-256 compared with the parent config descriptor.
- Evidence destination: a new stage directory created only after approval.
- Error handling: no automatic retry, no alternate host, no alternate digest.
- Stop conditions: redirect, proxy, TLS failure, challenge mismatch, unexpected status, oversized body, digest mismatch, size mismatch, malformed JSON, unsupported schema, any layer or package request.

No blob endpoint is authorised by this document.
