# G.14.7 Gate B approval matrix

Gate B is not granted. A synthetic workflow does not change any row below.

| Step | Decision |
| --- | --- |
| Package metadata | NOT APPROVED. Fixtures are `SYNTHETIC_TEST_ONLY`. |
| Wheel-only resolution | OFFLINE POLICY TESTED. Native compatibility is not verified. |
| Wheel downloads | NOT APPROVED. No sender. No network. |
| Artifact verification | OFFLINE ON SYNTHETIC BYTES. Real wheel metadata is not verified. |
| Lockfile generation | NOT APPROVED. The only lock written is marked `SYNTHETIC_TEST_ONLY`. |
| Candidate packaging | NOT APPROVED. |
| Docker metadata | NOT APPROVED. Base-image registry digest is unverified. |
| Docker build | NOT GRANTED. |
| Image export | NOT GRANTED. |
| Isolated runtime test | NOT GRANTED. |
| Production deployment | NO-GO. |
| Rollback | NO-GO. `NO_VERIFIED_ROLLBACK_TARGET`. |

Package-source approval, if it is ever considered separately, still has to name the index host, artifact host, HTTPS-only behavior, ports, redirects, authentication, proxy, certificates, timeouts, retries, size limits, destination, retention, and the prohibitions on installation, source builds, and credentials. This stage does not supply that approval.
