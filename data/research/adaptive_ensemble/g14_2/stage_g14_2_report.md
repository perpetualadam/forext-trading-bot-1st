# STAGE G.14.2 — READ-ONLY DOCKER PREFLIGHT AND CANDIDATE BUILD APPROVAL REVIEW REPORT

## 1. Live safety

- Running container changed: no
- Docker commands executed: read-only metadata only (`docker version`, `docker info`, `docker container inspect`, `docker image inspect`, `docker image ls`, `docker system df`)
- Docker images built: no
- Docker images pulled: no
- Docker restarts: no
- Broker API requests: no
- Broker mutations: no
- Live-order authorisation: BLOCKED (`operator_preflight_blocked`), not read or written in this stage
- Active strategies: none of the six original strategies were activated
- Production database writes: no
- Consensus Forecast modified: no

## 2. Baseline integrity

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Initial working-tree status: modified Dockerfile, two scheduler files, three migrated tests, and untracked G.13 through G.14.1 files
- Dockerfile SHA-256: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- .dockerignore SHA-256: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`
- G.10 allowlist SHA-256: `b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4`
- Staging manifest digest: `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`
- Staging files: 63, with no additional files
- Staging bytes: 617279
- Independent verification: PASS
- Unexpected changes: none in the staging context. The two environment backups were not opened.

## 3. Docker daemon

- Docker server version: 29.1.3
- API version: 1.52
- OS/architecture: linux/amd64, Docker Desktop 4.57.0, WSL2 kernel 6.6.87.2
- Daemon reachable: yes
- Configuration modified: no
- Unexpected findings: none

## 4. Running production

- Container ID: `5fcbcff7173eee98f6228b901fab96fd24474038852ef1f4cc3fbccd138edd32`
- Image ID: `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`
- Running status: running
- Restart count: 0
- Identity matches expected: yes
- Container modified: no
- Classification: `RUNNING_PRODUCTION_IDENTITY_MATCHED`

## 5. Base image

- Requested base tag: `python:3.12-slim-bookworm`
- Locally available: yes
- Image ID: `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`
- Repository digest: the field returned `python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`, which is the same value as the image ID and has no registry hostname. It is not treated as a registry manifest digest.
- OS/architecture: linux/amd64
- Immutable identity established: local image ID only. A pin for `FROM` was not established.
- Base-image pull required: no, while this local tag and image ID remain. Recheck immediately before any build. Do not pull if the check fails.
- Classification: `BASE_IMAGE_DIGEST_UNVERIFIED`
- Known running container uses this base image directly: no
- Size evidence: `docker image inspect` reported 45452267 bytes; `docker image ls` displayed 189MB. Both figures are recorded.

## 6. Candidate tag

- Proposed tag: `forexttradingbot1st-g14-candidate:d080d89-4a458b4b`
- Already exists: no
- Existing image ID, if any: none
- Tag collision: no
- Proposed replacement tag, if required: none
- Availability classification: `CANDIDATE_TAG_AVAILABLE_AT_PREFLIGHT`
- The tag must be rechecked immediately before a build.

## 7. Storage

- Image storage usage: 33.24 GB across 11 images, 23.97 GB reported reclaimable
- Build-cache usage: 27.36 GB, 17.98 GB reported reclaimable
- Available disk space: 169.65 GB free on C:, which holds the Docker Desktop WSL disks
- Estimated build size: the staged context is 617279 bytes, but the image is not that small. The local base image is displayed at 189MB, and unpinned dependencies can add further layers. A planning allowance of several gigabytes remains far below free space.
- Storage sufficient: yes, for one candidate build
- Cleanup performed: no

## 8. Network and dependencies

- Base-image network requirement: not required while the recorded local image remains
- Pip network requirement: required
- Requirements fully pinned: no
- Wheelhouse available: no
- Build-time scripts: pip upgrade and `pip install -r requirements.txt`, including possible package installation hooks
- Network-isolated build feasible: no
- Reproducibility limitations: `PYTHON_DEPENDENCY_RESOLUTION_UNPINNED`, `NETWORK_REQUIRED`, `BASE_IMAGE_DIGEST_UNVERIFIED`. Default build-cache reuse can also hide which package versions were selected.

## 9. Revised build proposal

- Exact proposed command: `docker build --pull=false --progress=plain -f "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2\Dockerfile" -t forexttradingbot1st-g14-candidate:d080d89-4a458b4b "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2"`
- Context path: `C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2`
- Candidate tag: `forexttradingbot1st-g14-candidate:d080d89-4a458b4b`
- Pull policy: `--pull=false`. Abort if the local base image ID has changed. Do not pull.
- Network policy: default build network stays enabled for pip. This is not an offline build.
- Cache policy: default cache remains enabled
- Credentials passed: none
- Running-production isolation: the command does not start, stop, or retag the running container
- Build approved: no

## 10. Candidate inspection plan

- Image metadata: later `docker image inspect` of the candidate tag only
- Image history: later `docker image history` of the candidate tag only
- Image export: later `docker image save` to `C:\Users\Brian\AppData\Local\Temp\forext-g14-2-candidate\`, outside OneDrive
- Offline layer verification: parse that new archive; do not recreate the deleted G.12 archive
- Expected /app files: 61 application files
- Secret review: reject credentials, operational state, research files, and both backup filenames
- Runtime execution required: no
- Cleanup approval required: yes, before any future archive is deleted

## 11. Remaining blockers

- Safety-state compatibility: `SAFETY_STATE_FORWARD_COMPATIBILITY_UNVERIFIED`
- Live database compatibility: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`
- Shadow-mount compatibility: `SHADOW_MOUNT_COMPATIBILITY_UNVERIFIED`
- Verified rollback target: `NO_VERIFIED_ROLLBACK_TARGET`
- Candidate runtime validation: unverified
- Production deployment readiness: NO-GO
- Rollback: NO-GO

## 12. Tests

- Exact commands: recorded in `data/research/adaptive_ensemble/g14_2/test_results.json`
- Tests passed: 78
- Tests failed: 0
- Tests skipped: 0
- Ruff: pass
- Mypy: pass
- Untested behavior: the build itself, package resolution, and daemon handling of the staged context (`DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`)

## 13. Files changed

- Production Python: unchanged
- Dockerfile: unchanged
- .dockerignore: unchanged
- Compose: unchanged
- New tests: none
- G.14.2 artifacts: `data/research/adaptive_ensemble/g14_2/`
- Staging directory: retained and unchanged
- Running production: unchanged

## 14. Final classification

`DOCKER_PREFLIGHT_COMPLETE_BUILD_APPROVAL_REQUIRED`

This does not authorise the build, a deployment, or a rollback.

## 15. Approval request

Permission is requested for one later build, and only that build:

```text
docker build --pull=false --progress=plain -f "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2\Dockerfile" -t forexttradingbot1st-g14-candidate:d080d89-4a458b4b "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2"
```

Operations that require permission:

1. Send the 63 staged files to the Docker daemon as the build context.
2. Use the local image `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254` as `python:3.12-slim-bookworm`, after an immediate recheck of that ID.
3. Leave the build network enabled so pip can download unpinned packages and may run installation hooks.
4. Use the existing build cache.
5. Create the new local tag `forexttradingbot1st-g14-candidate:d080d89-4a458b4b` if it is still absent.

Not permitted by this request: an image pull, a push, a container start, a change to the running bot, a prune, or a deployment.
