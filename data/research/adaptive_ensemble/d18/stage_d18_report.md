# STAGE D.18 — TARGET RUNTIME PROFILE AND PLATFORM IDENTITY VERIFICATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: `D18_AUDIT_COMPLETE_TARGET_SELECTION_REQUIRED`
- Gate A: PASS. Protected hashes matched. The D.18 directory was absent at the start.
- Gate B: PASS. The result is `TARGET_PLATFORM_UNSPECIFIED`.
- Gate C: PASS. The base-image tag is declared. The registry digest is missing. The historical local image ID is not a registry digest.
- Gate D: PASS. Python 3.12 is declared. Patch, ABI, and libc version are missing.
- Gate E: PASS. Four direct native candidates are named. No wheel is verified.
- Gate F: PASS. Command and working directory are declared. User, bot health check, and bot restart policy are missing.
- Gate G: PASS. The next stage is a user selection, not a registry call.
- Gate H: PASS. Dependency resolution is `TARGET_SELECTION_REQUIRED`.
- Critical findings: D18-PLATFORM-01, D18-BASE-01, D18-PYTHON-01, D18-LIBC-01, D18-WHEEL-01, D18-RUNTIME-01, D18-PROV-01.
- Target selection required: yes
- Target identity verified: no
- Dependency resolution eligible: no
- Production source modified: no
- Recommended next stage: an explicit user decision that names the OCI platform and confirms the registry. It is not started here.

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
- Live-order authorisation: historically BLOCKED. Current production state was not verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before this stage. HEAD does not identify the working-tree bytes.
- Protected source hashes: matched for `app.py`, `telegram_control.py`, `database.py`, `live_safety.py`, and `strategy_meta.py`.
- Requirements hashes: matched.
- Dockerfile hash: matched `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`.
- .dockerignore hash: matched.
- Compose hash: matched.
- Unexpected changes: none caused by this stage.

## 4. TARGET DECLARATIONS

- Dockerfile base reference: `python:3.12-slim-bookworm`, line 2.
- Dockerfile platform: absent.
- Compose platform: absent. That absence is not `linux/amd64`.
- Intended OS: Linux, inferred from the Debian tag. Not an OCI field in the file.
- Intended architecture: `TARGET_PLATFORM_UNSPECIFIED`.
- Python major/minor: 3.12, declared.
- Python patch: missing.
- Runtime stage: the only stage. No build stage.
- Entrypoint: no `ENTRYPOINT` instruction.
- Command: `uvicorn forex_bot.app:app --host 0.0.0.0 --port 8000`.

## 5. OCI PLATFORM IDENTITY

- Operating system: inferred Linux.
- Architecture: unspecified.
- Variant: unspecified.
- Index digest: missing.
- Platform manifest digest: missing.
- Configuration digest: missing.
- Local image ID: historical only, `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`.
- Identity limitations: a local image ID, a tag, and a registry digest are different. The historical `linux/amd64` notes describe a past Docker Desktop image. They were not used to select a target.

## 6. BASE-IMAGE PROVENANCE

- Registry: hostname not written in the Dockerfile. A default registry is an inference.
- Repository: `python`, declared.
- Tag: `3.12-slim-bookworm`, declared and mutable.
- Registry digest: missing. G.14.5 recorded it as unknown.
- Historical local image ID: the hash above. G.14.2 repeated it without a registry hostname.
- Manifest provenance: not present.
- Independent verification: not performed.
- Remaining gaps: index digest, platform manifest, configuration digest, layer digests, availability, and provenance.

## 7. PYTHON AND LIBC

- Python implementation: CPython, inferred from the image name. The image was not inspected.
- Python major/minor: 3.12, declared.
- Python patch: missing.
- ABI: missing.
- Linux distribution: Debian, inferred from `bookworm`.
- Distribution revision: missing. The codename is not a point release.
- libc family: glibc, inferred. The Alpine database image is a different service.
- libc version: missing.
- Native libraries: names of four direct candidates only.
- Host-target separation: the D.17 host interpreter was 3.13.5 on the audit workstation. It is not a resolution input. No host lock was made.

## 8. WHEEL COMPATIBILITY

- Direct native candidates: numpy, pandas, psycopg2-binary, and uvicorn with the `standard` extra.
- Possible transitive native dependencies: event-loop and HTTP accelerators from that extra, plus TLS libraries through requests. They are not a resolved closure.
- Wheel tag evidence: none.
- Architecture compatibility: unverified.
- ABI compatibility: unverified.
- libc compatibility: unverified.
- Wheel availability: no local wheels.
- Required future verification: exact artifact metadata after the platform, patch, ABI, and libc version exist.

## 9. RUNTIME CONFIGURATION

- Runtime user: undeclared.
- Working directory: `/app`.
- Entrypoint: undeclared.
- Command: the uvicorn command above.
- Environment variable names: declared on the bot service. Values were not read.
- Required mounts: `./data/ops` and `./data/research/v2_shadow`, as Compose text. Production mounts were not read.
- Writable paths: those two container paths are declared. Other write paths are unknown.
- Health checks: none on the bot. The database service has its own check.
- Restart policy: omitted on the bot. Ollama's `unless-stopped` is not the bot policy. Historical production restart was `no` and was not reinspected.
- Production compatibility: unverified.

## 10. TARGET PROFILE MATRIX

- Total fields: 30
- VERIFIED: 0
- DECLARED: 7
- INFERRED: 4
- PARTIAL: 2
- MISSING: 17
- BLOCKED_BY_SCOPE: 0
- NOT_APPLICABLE: 0
- Critical missing fields: architecture, variant, all three digest classes, Python patch, ABI, distribution revision, libc version, wheel tags, and provenance.

## 11. FUTURE VERIFICATION PLAN

- Target-selection decision: required first. Existing files cannot supply the architecture.
- Registry verification: after selection, a read-only manifest request. No pull.
- Image metadata verification: only if labels omit patch, distribution revision, or libc.
- Python patch verification: from that metadata.
- ABI verification: after implementation, patch, and architecture are known.
- libc verification: from image metadata, not from the word bookworm.
- Wheel-tag verification: after the target profile, in a separate package-metadata stage.
- Native-library verification: from the selected wheel metadata.
- Required network access: none for the selection decision. A later manifest read needs its own approval.
- Required Docker access: none for the selection decision or for a manifest read.
- Required production access: none.
- Required explicit approvals: selection, then registry read, then any image metadata inspection, then any package-metadata read. They stay separate.

## 12. DEPENDENCY-LOCK ELIGIBILITY

- Classification: `TARGET_SELECTION_REQUIRED`
- Sufficient target evidence: no
- Blocking fields: architecture, index digest, platform manifest digest, Python patch, ABI, libc version, and wheel tags.
- Permitted next step: the user names the platform and confirms the registry.
- Prohibited next step: resolution, lock creation, image pull, Docker, and production inspection.

## 13. FINDING REGISTER

- D18-PLATFORM-01. Dockerfile line 2 and the Compose bot service declare no platform. Current local file. This blocks a lock, a candidate image, and deployment. The future action is a user selection. No network, Docker, or production inspection is required for that decision. Production impact: UNVERIFIED.
- D18-BASE-01. The tag is mutable and has no digest. The historical local ID is not a registry digest. Current local file, with historical context. This blocks a platform-specific lock, a reproducible image, and deployment. A later registry read needs approval and network. Production impact: UNVERIFIED.
- D18-PYTHON-01. Minor 3.12 is declared. Patch and ABI are not. This blocks exact wheel selection, a candidate image, and deployment. Production impact: UNVERIFIED.
- D18-LIBC-01. glibc is an inference and the version is absent. This blocks a manylinux policy, a candidate image, and deployment. Production impact: UNVERIFIED.
- D18-WHEEL-01. The four native candidates have no verified wheels. This blocks resolution, a candidate image, and deployment. Production impact: UNVERIFIED.
- D18-RUNTIME-01. User, bot health check, and bot restart policy are undeclared. This does not by itself choose wheel tags. It blocks a complete candidate runtime and deployment. Production impact: UNVERIFIED.
- D18-PROV-01. No current registry provenance, SBOM, or attestation was identified. This blocks trusted artifact selection, a candidate image, and deployment. Production impact: UNVERIFIED.

None of these findings were repaired.

## 14. VALIDATION

- Commands executed: Git HEAD, branch, targeted status, SHA-256 of the ten protected files, and SHA-256 of four local scripts.
- Files read: Dockerfile, Compose, requirements, the example collector script, D.16 and D.17 target evidence, and the cited G.14 provenance pages.
- Files created: the D.18 research files under `data/research/adaptive_ensemble/d18/`.
- Files modified: none outside that new directory.
- Static checks: JSON artifacts parse. Protected hashes were compared before the write and again after it.
- Runtime tests: none
- Docker commands: none
- Network requests: none
- Package-manager commands: none
- Prohibited operations: none observed
- Missing evidence: architecture, registry hostname, all digest classes, Python patch, ABI, libc version, wheel tags, and provenance.

## 15. FINAL CLASSIFICATION

`D18_AUDIT_COMPLETE_TARGET_SELECTION_REQUIRED`

## 16. NEXT ACTION

D.18 completed. The target platform was not selected. The target platform was not verified. The base-image digest was not verified. The Python patch was not verified. libc compatibility was not verified. Wheel compatibility was not verified. Dependency resolution is not authorised. Production source remained unchanged.

The bot may not be restarted. An image may not be built. Deployment is not authorised. Live trading is not authorised. Another separately approved stage is required. The next one is a user target-selection decision.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
