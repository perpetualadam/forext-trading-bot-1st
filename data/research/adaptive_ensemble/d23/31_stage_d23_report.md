# STAGE D.23 — DUAL-ARCHITECTURE RUNTIME METADATA VERIFICATION PLANNING REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D23_OFFLINE_EVIDENCE_REVALIDATED_PLANNING_COMPLETE`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS
- Gate F: PASS
- Gate G: PASS
- Gate H: PASS
- Gate I: PASS
- Production source modified: no
- Network requests: 0
- Index locally revalidated: yes
- AMD64 manifest locally revalidated: yes
- ARM64 manifest locally revalidated: yes
- Config descriptors extracted: yes
- Recommended next action: a separate approval is required before any config-blob request. D.24 was not started.

This classification revalidates preserved manifest bytes and extracts config descriptors. It does not verify the contents of either image configuration blob.

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: none
- Broker mutations: none
- Production database access: none
- Telegram network requests: none
- Operational-state access: none
- Shadow-mount access: none
- Docker commands: none
- WSL commands: none
- VM commands: none
- Network requests: none
- Image downloads: none
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before D.23. HEAD does not identify the working-tree bytes.
- Protected hashes: all ten expected digests are 64 hexadecimal characters and match the current files and the D.21 baseline.
- Previous-stage evidence integrity: the original D.22 stop remains `D22_BLOCKED_BASELINE_INTEGRITY`. The three D.22-R1 raw manifests rehash to their recorded digests.
- Unexpected changes: none caused by this stage.

## 4. OCI INDEX REVALIDATION

- Expected digest: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`
- Actual digest: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`
- Expected size: 6546
- Actual size: 6546
- Media type: `application/vnd.oci.image.index.v1+json`
- Schema version: 2
- Descriptor count: 10
- Cross-reference verdict: the local digest matches the preserved registry-reported digest. The mutable tag was not resolved again.

## 5. AMD64 MANIFEST REVALIDATION

- Expected digest: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`
- Actual digest: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`
- Expected size: 1752
- Actual size: 1752
- Parent descriptor: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, size 1752, platform linux/amd64
- Media type: `application/vnd.oci.image.manifest.v1+json`
- Schema version: 2
- Verification verdict: locally revalidated

## 6. ARM64 MANIFEST REVALIDATION

- Expected digest: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`
- Actual digest: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`
- Expected size: 1754
- Actual size: 1754
- Parent descriptor: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, size 1754, platform linux/arm64
- Variant: v8
- Media type: `application/vnd.oci.image.manifest.v1+json`
- Schema version: 2
- Verification verdict: locally revalidated

## 7. CONFIGURATION DESCRIPTORS

AMD64:

- Parent manifest: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`
- Config media type: `application/vnd.oci.image.config.v1+json`
- Config digest: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`
- Config size: 5684
- Config blob obtained: no
- Config contents verified: no

ARM64:

- Parent manifest: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`
- Config media type: `application/vnd.oci.image.config.v1+json`
- Config digest: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`
- Config size: 5699
- Config blob obtained: no
- Config contents verified: no

The config descriptor records the blob referenced by the verified manifest. The two config digests differ. Neither digest is the index digest, the platform-manifest digest, or a local Docker image ID.

Both manifests also contain literal annotations. `org.opencontainers.image.version` is `3.12.15-slim-bookworm` and `org.opencontainers.image.base.name` is `debian:bookworm-slim` on both platforms. The annotated Debian base digests differ by platform. Those annotations are preserved strings. They are not measured runtime versions.

## 8. RUNTIME EVIDENCE MATRIX

- Total platform-property entries: 48
- Verified from local bytes: 4
- Verified descriptor only: 2
- Declared in local source: 4
- Historical observation: 0
- Inferred: 0
- Unverified: 16
- Missing: 20
- Blocked: 2

Status detail: VERIFIED_FROM_LOCAL_BYTES 4, VERIFIED_DESCRIPTOR_ONLY 2, DECLARED_IN_LOCAL_SOURCE 4, UNVERIFIED 16, MISSING 20, BLOCKED 2.

## 9. FUTURE VERIFICATION PLAN

- Config blob verification procedure: twenty offline-designed controls in `13_future_config_blob_verification_plan.md`, using the two config digests above.
- Proposed registry boundary: `registry-1.docker.io` and, only for a matching challenge, `auth.docker.io`.
- Proposed request budget: 4 GET requests.
- Proposed response-size limits: 1 MiB transport cap and exact descriptor sizes 5684 and 5699.
- Proposed TLS controls: certificate and hostname verification, no redirect following, no proxy bypass.
- Proposed digest checks: raw-byte SHA-256 and exact size against the parent config descriptor.
- Proposed runtime checks: class A fields only after a blob match. Class B, C, D, and E remain separate.
- Proposed provenance checks: signatures and attestations remain a separate review.
- Current network authorisation: none.

## 10. FINDINGS

- D23-HIST-01. Evidence: the original D.22 record remains `D22_BLOCKED_BASELINE_INTEGRITY`. Evidence level: preserved historical record. Impact: the retry does not erase that stop. Required action: leave D.22 unchanged. Required approval: none for preservation. Production impact: UNVERIFIED.
- D23-CFG-01. Evidence: both config descriptors were extracted and neither blob is local. Evidence level: descriptor only. Impact: config contents remain unread. Required action: do not retrieve blobs in D.23. Required approval: a separate config-blob approval. Production impact: UNVERIFIED.
- D23-ANN-01. Evidence: both manifests carry the literal version string `3.12.15-slim-bookworm` and base name `debian:bookworm-slim`. Evidence level: literal manifest annotation. Impact: the strings are not measured Python, Debian package, or libc versions. Required action: keep those runtime properties unverified or missing. Required approval: a later class A, B, or C stage. Production impact: UNVERIFIED.
- D23-TAG-01. Evidence: Dockerfile uses the mutable tag `python:3.12-slim-bookworm` without the verified index digest. Evidence level: local source declaration. Impact: the build reference can move. Required action: leave the Dockerfile unchanged. Required approval: a later pinning decision, if requested. Production impact: UNVERIFIED.
- D23-PLAT-01. Evidence: one linux/amd64 descriptor and one linux/arm64 variant v8 descriptor were selected from ten index entries. Evidence level: local bytes. Impact: the other eight descriptors stay out of scope. Required action: do not retrieve them here. Required approval: a new approval for any other descriptor. Production impact: UNVERIFIED.
- D23-NAT-01. Evidence: nine unpinned production requirements and missing D.17 wheel tags. Evidence level: declared lower bounds. Impact: native compatibility remains unknown on both platforms. Required action: leave resolution unauthorised. Required approval: a later dependency stage. Production impact: UNVERIFIED.
- D23-PROV-01. Evidence: digest equality covers the preserved index and two manifests. Evidence level: byte identity. Impact: publisher authenticity and rollback remain unverified. Required action: keep provenance unverified. Required approval: a separate provenance review. Production impact: UNVERIFIED.

## 11. VALIDATION

- Commands executed: Git HEAD, branch, targeted status, and Python standard-library hashing and JSON parsing.
- Files read: the ten protected files, Dockerfile, requirements files, D.17 native-wheel evidence, D.21 policy and baseline records, the original D.22 stop record, and the D.22-R1 manifests and digest records.
- Files created: the D.23 evidence under `data/research/adaptive_ensemble/d23/`.
- Files modified: none outside that new directory.
- Local digest checks: protected files, index, AMD64 manifest, and ARM64 manifest.
- Static checks: OCI schema, descriptor syntax, Dockerfile text, and requirements text.
- Network requests: none.
- Docker commands: none.
- Prohibited operations: none observed.

## 12. FINAL CLASSIFICATION

`D23_OFFLINE_EVIDENCE_REVALIDATED_PLANNING_COMPLETE`

## 13. NEXT ACTION

D.23 completed the offline revalidation and planning work. All three raw manifests were revalidated. Config descriptors were extracted. Config blob contents were not verified. Python patch versions were not verified. Python ABI was not verified. libc versions were not verified. Wheel compatibility was not verified. Dependency resolution is not authorised. Network access is not authorised. Image building is not authorised. Production deployment is not authorised. Live trading is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
