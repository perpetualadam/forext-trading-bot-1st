# STAGE G.14.6 — OFFLINE DEPENDENCY ACQUISITION SECURITY REMEDIATION REPORT

## 1. Live safety

The running container was not changed. No Docker command, image build, image pull, network request, dependency download, package installation, or third-party package execution occurred. No broker request or mutation occurred. Live-order authorisation was not read or changed. No strategy was activated. The production database, operational state, and shadow mounts were not accessed. The Consensus Forecast project was not modified.

## 2. Baseline integrity

Git HEAD is `d080d897945bc44fa37c02caab504ed707146bec` on `main`. The Dockerfile, `.dockerignore`, G.10 allowlist, and frozen G.7 and G.10 archives and manifests match the expected hashes. Pre-existing uncommitted work was left in place.

## 3. Staging context

`C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2` still has 63 files and 617279 bytes. The manifest digest matches. Independent verification passed. The directory was not modified. The sensitive backup files were not opened.

## 4. Remediation summary

G14.5-01 through G14.5-07 are `RESOLVED_AND_INDEPENDENTLY_VERIFIED`. G14.5-08 needed no change and import remains offline. Details are in `finding_by_finding_reaudit.json`.

## 5. Acquisition helper

Environment isolation, interpreter selection, pip-setting rejection, proxy rejection, index checks, artifact-host checks, redirect checks, HTTPS checks, and wheels-only checks are on `prepare_acquisition`. `commit_acquisition` repeats the URL check and then refuses to send. Import does not open a network client. A live end-to-end download was not tested. Gate B was not granted.

## 6. Wheel verifier

SHA-256, size, ZIP structure, resource limits, METADATA, WHEEL, RECORD, tags, and the metadata dependency graph are required before acceptance. Provenance for these fixtures remains synthetic. A production lock is still refused.

## 7. Requirement parser

The production file still has nine direct requirements. Extras and markers are preserved. Direct URLs, VCS forms, and pip directives are rejected. The production lines have no markers.

## 8. Filesystem safety

Repository, OneDrive, staging, nonempty, symlink, reparse, parent-link, traversal, case-collision, replacement, partial, and interrupted-write cases fail closed. Files are created with `O_EXCL`. A concurrent parent replacement remains a residual limit.

## 9. Synthetic security tests

The 100 required negative cases were executed and failed closed. None were skipped. No real network request, download, or package execution occurred.

## 10. Independent re-audit

Seven findings are resolved on the acceptance path. None are partial or unresolved. No new critical or high finding was opened. Gate B execution is not authorised.

## 11. Target compatibility

The intended target remains Linux x86_64 CPython 3.12. Patch version, SOABI, glibc, pip version, and exact native wheel tags are unknown. Classification: `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`.

## 12. Base image

The requested tag is `python:3.12-slim-bookworm`. The historical local image ID is `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`. The registry manifest digest is UNKNOWN. Classification: `BASE_IMAGE_DIGEST_UNVERIFIED`.

## 13. Approval matrix

Every permission from package metadata through rollback is NOT GRANTED.

## 14. Remaining blockers

Package source approval, a live transport, a real lock, a verified wheelhouse, target compatibility, the base-image digest, the pip toolchain version, Docker context behavior, safety-state compatibility, live database compatibility, shadow-mount compatibility, and a verified rollback target remain open. Production deployment is NO-GO.

## 15. Tests

The scoped pytest command passed 140 tests, with 0 failed and 0 skipped. Ruff and Mypy passed on the remediated modules. Historical G.10 snapshot tests were not run.

## 16. Files changed

No production Python, Dockerfile, `.dockerignore`, `requirements.txt`, or Compose file was changed by this stage. The acquisition helper, verifier, and inventory helper were remediated. New tests are `tests/test_g14_6_security.py`. G.14.6 artifacts are under `data/research/adaptive_ensemble/g14_6/`. The staging directory and the running production system were not changed.

## 17. Final classification

`G14_6_OFFLINE_REMEDIATION_COMPLETE_GATE_B_APPROVAL_REQUIRED`

## 18. Next action

The seven findings are resolved in the offline tools. Gate B is not approved and must not be executed. A live download client, real wheels, and the target compatibility profile are still absent. Package-source approval is still required. Docker, network access, deployment, and rollback each need a separate approval. No network operation is authorised.

GATE B APPROVAL: NOT GRANTED.
DOCKER BUILD APPROVAL: NOT GRANTED.
PRODUCTION DEPLOYMENT: NO-GO.
ROLLBACK: NO-GO.
