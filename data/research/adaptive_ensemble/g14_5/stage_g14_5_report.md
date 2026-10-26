# STAGE G.14.5 — DEPENDENCY ACQUISITION SECURITY REVIEW AND TARGET COMPATIBILITY VERIFICATION REPORT

## 1. Live safety

The running container was not changed. No Docker command, image build, image pull, network request, dependency download, or package installation occurred. No broker request or broker mutation occurred. Live-order authorisation was not read or changed and remains blocked from the prior record. No strategy was activated. The production database, operational state, and shadow mounts were not accessed. The Consensus Forecast project was not modified.

## 2. Baseline integrity

Git HEAD is `d080d897945bc44fa37c02caab504ed707146bec` on `main`. The Dockerfile, `.dockerignore`, G.10 allowlist, frozen G.10 archive and manifest, and frozen G.7 archive and manifest match the expected hashes. The pre-existing uncommitted working tree was left in place and was not committed.

## 3. Staging context

`C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2` still has 63 files and 617279 bytes. The manifest digest is `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`. Independent verification passed. Both sensitive backup names are absent. The directory was not modified.

## 4. Acquisition helper audit

`tests/g14_4_acquire.py` only decides whether a destination directory is allowed. Importing it opens no network client and starts no subprocess. It does not isolate pip configuration, enforce an index host, enforce an artifact host, restrict redirects, or apply a wheels-only download flag. It does not reject a symlink before `Path.resolve`. Findings G14.5-01, G14.5-02, G14.5-03, and G14.5-07 are open. Classification: the helper does not enforce a network acquisition policy.

## 5. Independent verifier audit

`tests/g14_4_verify.py` checks hashes, sizes, filename tags, suffix-based source distributions, manifest dependency names, and synthetic provenance. It does not validate ZIP structure, `WHEEL`, `METADATA`, `RECORD`, compression limits, or markers. A non-zip payload with a matching hash is accepted. Findings G14.5-04 and G14.5-05 are open. Hash verification is not archive or graph verification.

## 6. Inventory helper audit

`tests/g14_4_inventory.py` counts the nine direct requirements and records bracket extras. It sets every environment marker to `None`. It stores a direct URL requirement and a `git+` requirement as ordinary constraints. Finding G14.5-06 is open.

## 7. Pip environment isolation

Inherited index, find-links, trusted-host, binary policy, proxy, and certificate settings are not filtered because no acquisition subprocess exists. The proposed isolation is an explicit allowlist, not a copy of the host environment and not `PIP_CONFIG_FILE` alone. That design is not implemented.

## 8. Network and redirect policy

The proposed index `https://pypi.org/simple` is not approved. `files.pythonhosted.org` is only a proposed artifact host. HTTPS, redirect hosts, and TLS checks are not implemented in the helper. Additional and unknown hosts are not blocked by code. `ARTIFACT_HOST_POLICY_NOT_ENFORCED`.

## 9. Wheels-only and archive safety

Wheels-only download is not enforced. Source distributions are blocked only when the filename suffix matches the verifier's list. Unsupported tags are blocked at filename level. Malformed ZIP files, ZIP traversal, and ZIP bombs are not rejected. `WHEELS_ONLY_ENFORCEMENT_INCOMPLETE`.

## 10. Dependency graph

Nine direct requirements are known. The full transitive graph is not known. Completeness is not enforced from wheel metadata. Extras and markers are not evaluated for the target. `DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED`.

## 11. Target compatibility

The intended target is Linux, x86_64, CPython 3.12. The patch version, SOABI, glibc, pip version, and exact native wheel tags are unknown. Existing reports and source files do not supply those values. Docker metadata, an image export, or an isolated interpreter probe would each require a separate approval. `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`.

## 12. Base image

The requested tag is `python:3.12-slim-bookworm`. The historical local image ID is `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`. The registry manifest digest is UNKNOWN. An immutable `FROM` digest is not available. `BASE_IMAGE_DIGEST_UNVERIFIED`.

## 13. Security findings

G14.5-01 through G14.5-06 are HIGH. G14.5-07 is MEDIUM. G14.5-08 records that import time stays offline and does not block Gate B. None of the HIGH or MEDIUM remediations was implemented. Each open finding blocks Gate B. Details are in `security_findings.json`.

## 14. Approval matrix

Package metadata, wheel-only resolution, wheel downloads, hash verification, metadata verification, lockfile generation, candidate packaging, Docker metadata, Docker build, image export, isolated runtime testing, production deployment, and rollback are all NOT GRANTED.

## 15. Remaining blockers

Package source approval is required. Acquisition helper security, wheel verifier security, the dependency lock, and a verified wheelhouse remain open. The base-image registry digest, pip toolchain version, and target compatibility profile remain unverified. Docker daemon context behavior, safety-state compatibility, live database compatibility, and shadow-mount compatibility remain unverified. There is no verified rollback target. Production deployment is NO-GO.

## 16. Tests

The scoped pytest command covering the G.13, G.13.1, G.14, G.14.1, G.14.3, G.14.4, and G.14.5 suites passed 93 tests, with 0 failed and 0 skipped. Ruff and Mypy passed on the new G.14.5 modules. Historical G.10 snapshot tests were not run. The new tests use synthetic text and one non-zip temporary file. They show missing controls; they do not simulate live network behavior. Protected production files were not changed by the tests.

## 17. Files changed

No production Python, Dockerfile, `.dockerignore`, `requirements.txt`, or Compose file was changed. New files are `tests/g14_5_audit.py`, `tests/test_g14_5_security.py`, and the G.14.5 research artifacts. The staging directory and the running production system were not changed.

## 18. Final classification

`GATE_B_SECURITY_REMEDIATION_REQUIRED`

## 19. Next action

Gate B is not security-ready. Offline remediation of findings G14.5-01 through G14.5-07 is required before any download approval is considered. Target compatibility evidence remains incomplete. Docker metadata, an interpreter probe, network access, a build, deployment, and rollback each need a separate approval. No network operation is authorised.

GATE B APPROVAL: NOT GRANTED.
DOCKER BUILD APPROVAL: NOT GRANTED.
PRODUCTION DEPLOYMENT: NO-GO.
ROLLBACK: NO-GO.
