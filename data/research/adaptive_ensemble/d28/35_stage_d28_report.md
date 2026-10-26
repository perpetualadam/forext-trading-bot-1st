# STAGE D.28 — OFFLINE PYTHON ABI AND LIBC EVIDENCE ACQUISITION PLANNING REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D28_OFFLINE_ABI_LIBC_PLANNING_COMPLETE`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS
- Gate F: PASS
- Gate G: PASS
- Gate H: PASS
- Gate I: PASS
- Gate J: PASS
- Production source modified: no
- Network requests: 0
- Image layers downloaded: none
- Runtime execution: none
- Recommended next action: if a further approval is sought, limit it to downloading the already identified compressed layer blobs, without extraction. That download would not measure ABI or libc.

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
- Image-layer downloads: none
- Image-layer extraction: none
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before D.28. HEAD does not identify the working-tree bytes.
- Protected hashes: the ten expected digests match the current files.
- Earlier evidence integrity: D.22 through D.27 were unchanged.
- Unexpected changes: none caused by this stage.

## 4. OCI EVIDENCE

- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes
- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes
- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes
- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes
- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes
- Descriptor relationships: index, manifests, and config descriptors agree.
- OCI integrity verdict: both configs declare PYTHON_VERSION=3.12.15. ARM64 variant is v8. Layer bytes are not local.

## 5. PYTHON ABI REQUIREMENTS

- AMD64 checklist: 25 items, recorded and not measured.
- ARM64 checklist: 25 items, recorded and not measured.
- Evidence available from config: the version declaration and platform fields only.
- Evidence requiring filesystem inspection: executable hash, ELF architecture, sysconfigdata, and extension suffixes, after verified layers exist.
- Evidence requiring execution: live sys values and the interpreter's accepted wheel-tag set.
- Evidence requiring target VPS access: none of the base-image questions. VPS identity is a separate gap.
- Remaining unknowns: implementation, patch measurement, SOABI, ABI flags, and supported tags.

## 6. LIBC REQUIREMENTS

- AMD64 checklist: 25 items, recorded and not measured.
- ARM64 checklist: 25 items, recorded and not measured.
- glibc questions: family and version are not inferred from bookworm.
- musl questions: absence of musl is not inferred from the image name.
- Native dependency questions: direct ELF dependencies can be read statically later. dlopen closures cannot.
- Static inspection possibilities: libc path, hash, PT_INTERP, and symbol versions present in files.
- Execution requirements: effective loader search and runtime acceptance.
- Remaining unknowns: libc family, libc version, and manylinux or musllinux relevance.

## 7. INSPECTION METHOD COMPARISON

- Config-only: exhausted for ABI and libc.
- Static layers: can identify files and ELF metadata after a verified download and a separate extract approval.
- Isolated runtime: can read sys values and tag acceptance, and it executes code.
- Final bot image: not built, and it would include dependency installation.
- Actual VPS: production access, and it may differ from this snapshot.
- Relative risk: config-only is lowest, then download-only, then static extract, then runtime, then final image, then VPS.
- Relative cost: layer downloads are the first large byte cost. Declared compressed totals are in the layer inventories.
- Relative evidence quality: runtime is broader, static files are safer for file identity, and neither proves the VPS.
- Required permissions: each method after config-only needs a new approval.

## 8. OCI LAYER INVENTORY

- AMD64 layer descriptors: 4, compressed total 47558478 bytes.
- ARM64 layer descriptors: 4, compressed total 47168483 bytes.
- Compressed digests: recorded from the manifests. The blobs are not local.
- Compressed sizes: recorded from the manifests.
- Rootfs diff IDs: 4 AMD64 and 4 ARM64 uncompressed identifiers.
- Descriptor relationships: compressed digests and diff IDs are different identifier types.
- Missing information: layer bytes, uncompressed tar bytes, and file lists.

## 9. FUTURE NETWORK BOUNDARY

- Proposed hosts: `registry-1.docker.io` for blob GET, and `auth.docker.io` only if a later approval repeats anonymous authentication.
- Proposed methods: GET.
- Proposed request budget: one GET for each declared layer, status PROPOSED_NOT_AUTHORISED.
- Proposed byte budget: the declared compressed totals. A response cap is MISSING.
- Proposed duration: MISSING.
- Proposed redirect policy: do not follow.
- Proposed authentication policy: not authorised now.
- Proposed integrity controls: stream-hash each blob and stop on mismatch.
- Proposed storage controls: the historical CloudFront host is not approved.
- Approval status: NOT AUTHORISED.

## 10. TRUST AND PROVENANCE

- Evidence acceptance levels: six levels, and only Level 1 is present.
- Mutable-tag risks: `python:3.12-slim-bookworm` can move away from this snapshot.
- Digest-pinning requirements: later work must name the manifest digests above.
- Artifact integrity: compressed and uncompressed hashes must both be checked when each exists.
- Publisher authenticity: a digest match does not establish it.
- Runtime measurement limitations: static files do not prove process behaviour.
- VPS applicability: base-image evidence does not identify the deployment host.

## 11. FINDINGS

- D28-BASE-01. Evidence: verified config bytes. Evidence classification: VERIFIED_CONFIG_DECLARATION. Supported conclusion: both configs declare PYTHON_VERSION=3.12.15. Unsupported conclusion: that string is a measured ABI. Impact: config analysis is exhausted for this question. Required next evidence: interpreter or filesystem measurement. Required approval: yes. Production impact: UNVERIFIED.
- D28-PYTHON-01. Evidence: no probe output. Evidence classification: MISSING. Supported conclusion: implementation and patch were not measured. Unsupported conclusion: the image contains a measured CPython build. Impact: wheel selection remains conditional. Required next evidence: static files or an isolated probe. Required approval: yes. Production impact: UNVERIFIED.
- D28-ABI-01. Evidence: no SOABI or tag probe. Evidence classification: MISSING. Supported conclusion: D.27 tag counts are screening outputs. Unsupported conclusion: the interpreter accepts those tags. Impact: the 1218, 714, and 708 figures stay unqualified. Required next evidence: sysconfigdata or a runtime tag list. Required approval: yes. Production impact: UNVERIFIED.
- D28-LIBC-01. Evidence: bookworm annotation and no libc file. Evidence classification: UNVERIFIED. Supported conclusion: the annotation names debian:bookworm-slim. Unsupported conclusion: glibc or musl version is known. Impact: manylinux and musllinux tags stay uncompared. Required next evidence: libc file identity. Required approval: yes. Production impact: UNVERIFIED.
- D28-LAYER-01. Evidence: manifest layer descriptors. Evidence classification: VERIFIED_OCI_DESCRIPTOR. Supported conclusion: compressed digests and sizes are recorded. Unsupported conclusion: the blobs were hashed locally. Impact: static inspection cannot start. Required next evidence: a download approval, then the blobs. Required approval: yes. Production impact: UNVERIFIED.
- D28-STATIC-01. Evidence: this plan. Evidence classification: PLANNED_NOT_EXECUTED. Supported conclusion: extraction needs traversal, link, device, and size limits. Unsupported conclusion: a matching digest makes extraction safe. Impact: download and extraction stay separate approvals. Required next evidence: a written extract sandbox. Required approval: yes. Production impact: UNVERIFIED.
- D28-EXEC-01. Evidence: no container was created. Evidence classification: PLANNED_NOT_EXECUTED. Supported conclusion: runtime questions need an isolated probe. Unsupported conclusion: Docker is already authorised. Impact: execution remains out of scope. Required next evidence: an execution approval if static inspection is insufficient. Required approval: yes. Production impact: UNVERIFIED.
- D28-ARCH-01. Evidence: platform descriptors and the Windows host. Evidence classification: NOT_EVALUATED. Supported conclusion: cross-architecture execution would need emulation that was not installed. Unsupported conclusion: emulation is available or faithful. Impact: an ARM64 measurement on this host is not assumed. Required next evidence: a named native or emulated environment. Required approval: yes. Production impact: UNVERIFIED.
- D28-PROV-01. Evidence: digest checks without signatures. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the five OCI files match their expected digests. Unsupported conclusion: the publisher is authenticated. Impact: trust stays at Level 1. Required next evidence: signatures only under a separate approval. Required approval: yes. Production impact: UNVERIFIED.
- D28-FINAL-01. Evidence: Dockerfile and base config are different documents. Evidence classification: DECLARED_IN_LOCAL_SOURCE. Supported conclusion: the bot command is a Dockerfile declaration, not the base Cmd. Unsupported conclusion: a base-image ABI is the final image ABI. Impact: final-image measurement remains future work. Required next evidence: a built image digest. Required approval: yes. Production impact: UNVERIFIED.
- D28-VPS-01. Evidence: no host inventory. Evidence classification: MISSING. Supported conclusion: linux/amd64 and linux/arm64/v8 are planning targets. Unsupported conclusion: the VPS matches either target. Impact: deployment suitability is open. Required next evidence: a receiver inventory. Required approval: yes. Production impact: UNVERIFIED.
- D28-SAFETY-01. Evidence: no production access. Evidence classification: NOT_EVALUATED. Supported conclusion: this plan did not read or change trading controls. Unsupported conclusion: live trading is safe. Impact: planning has no production effect. Required next evidence: a separately authorised production assessment. Required approval: yes. Production impact: UNVERIFIED.

## 12. FUTURE DECISION

- Recommended next stage: bounded compressed-layer acquisition without extraction, only after a new approval.
- Evidence gap addressed: missing Level 2 bytes. ABI and libc remain unmeasured until a later static inspection.
- Permissions required: named hosts, the exact layer digests, a byte cap, a duration cap, and a no-follow redirect rule.
- Risks: the declared compressed totals are 47558478 bytes for AMD64 and 47168483 bytes for ARM64. A redirect to an unnamed storage host must stop the stage.
- Remaining uncertainty: ABI, libc, wheel-tag acceptance, final image, VPS, and publisher identity.
- Explicit approval required: yes.

## 13. VALIDATION

- Commands executed: git HEAD, branch, targeted status, and standard-library JSON planning.
- Network requests: 0
- Files created: D.28 artifacts under data/research/adaptive_ensemble/d28/.
- Files modified: none outside that new directory.
- Protected source hashes: ten files matched.
- OCI hashes: five objects matched.
- Prior evidence hashes: reviewed D.25–D.27 files matched before and after.
- Prohibited operations: none observed.

## 14. FINAL CLASSIFICATION

`D28_OFFLINE_ABI_LIBC_PLANNING_COMPLETE`

## 15. NEXT ACTION

D.28 planning completed. No image layer was downloaded. No image layer was extracted. No interpreter was executed. Python ABI was not measured. libc was not measured. Docker was not executed. Production was not accessed. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
