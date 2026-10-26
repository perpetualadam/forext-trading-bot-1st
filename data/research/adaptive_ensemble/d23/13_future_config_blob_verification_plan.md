# Future config-blob verification plan

This procedure is designed for a separately approved stage. D.23 does not execute it. D.22-R1 manifest permission does not authorise it.

Parent evidence is the locally revalidated manifests:

- linux/amd64 manifest `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, config `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, size 5684.
- linux/arm64 variant v8 manifest `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, config `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, size 5699.

## Proposed procedure

1. Use the locally verified platform manifest as the parent. Do not rerequest the index in this procedure.
2. Take the AMD64 config digest `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`.
3. Take the AMD64 config size 5684.
4. Request that blob by immutable digest from `library/python` on a registry authority named in the future approval. The proposed authority is `registry-1.docker.io` and the proposed path is `/v2/library/python/blobs/sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`.
5. Restrict the repository to `library/python`.
6. Restrict the registry to the authority named by that separate approval.
7. Use an anonymous token only if a bearer challenge matches the separately approved token service, path, service, and scope. The proposed scope string is `repository:library/python:pull`. That string is a registry read scope. The future approval must explicitly cover these two config blobs.
8. Enforce TLS certificate and hostname verification.
9. Reject unexpected redirects without following them.
10. Reject unapproved proxies.
11. Read the body in bounded chunks. Stop if the body would exceed 1 MiB or the descriptor size.
12. Preserve the exact blob bytes.
13. Calculate SHA-256 of those exact bytes.
14. Require equality with the config descriptor digest.
15. Require the raw byte count to equal the descriptor size.
16. Parse the JSON only after the digest and size match.
17. Validate the fields the OCI image-config schema actually requires, including architecture, os, and rootfs, and record optional fields that are present.
18. Record only platform and image-configuration metadata supported by the parsed JSON.
19. List every property that still requires layer inspection or runtime execution.
20. Stop without requesting image layers.

The same twenty controls apply to the ARM64 config blob `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, size 5699, path `/v2/library/python/blobs/sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`.

## Interpretation limits

Configuration JSON may contain environment, command, entrypoint, user, labels, architecture, and operating-system fields. Those fields are class A evidence when present. This plan does not assume the JSON contains the Python patch version, the Python ABI, or the libc version. A label or annotation that names a version remains image metadata until a later class B or class C check measures it.

Acceptable HTTP Content-Type values must be chosen in the future approval before the request. Blob identity is the raw-byte digest. A Content-Type that differs from the descriptor media type is not permission to follow another URL. If the returned type is outside the pre-approved allowlist, stop.
