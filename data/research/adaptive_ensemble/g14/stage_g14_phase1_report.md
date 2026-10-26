# STAGE G.14 — PHASE 1 BUILD-CONTEXT AND CANDIDATE-IMAGE PREPARATION REPORT

## 1. Live safety

- Running container changed: no
- Docker commands executed: no
- Docker images built: no
- Docker restarts: no
- Broker API requests: no
- Broker mutations: no
- Live-order authorisation: `BLOCKED`, reason `operator_preflight_blocked`. The safety-state file was not written.
- Active strategies: none
- Production database writes: no
- Consensus Forecast modified: no

## 2. Baseline integrity

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec` on `main`
- Initial working-tree status: the G.13 Dockerfile, G.13 and G.13.1 tests and artifacts, the three migrated historical tests, and the two scheduler files
- Dockerfile SHA-256: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- `.dockerignore` SHA-256: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`
- G.10 allowlist SHA-256: `b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4`
- Frozen evidence verification: G.7 archive, G.7 canonical manifest, G.10 archive, and G.10 canonical manifest matched
- Unexpected changes: none. Test runs briefly rewrote three G.5/G.6 JSON files; those files were restored.

## 3. Build-context inventory

- Context source: the repository root, assessed with the local `.dockerignore` matcher
- Expected included files: 206 files, 1,516,574 bytes
- Expected excluded files: `.git`, `.env`, keys, `/data`, tests, reports, caches, and `docker-compose.yml`. 4,528 files were observed as excluded.
- Sensitive-file exposure: `main example .env backup.txt` and `# Copy to .env and fill in. docker.txt` are gitignored local secrets and are not ignored by `.dockerignore`. Their contents were not read.
- Symlink/reparse-point findings: none among the included files
- Windows path concerns: the matcher is case-sensitive and uses forward slashes. It is not the daemon. No case-variant credential names were included.
- Docker daemon behavior: `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`
- Classification: `BUILD_CONTEXT_EXPOSURE_BLOCKED`

The image `COPY` list does not include those backups. A build would still upload them. The context also includes 123 research Python files that are not copied into the image.

## 4. Dockerfile review

- Base image: `python:3.12-slim-bookworm`
- Base-image digest known: no
- Working directory: `/app`
- Dependency installation: `pip install --upgrade pip` and `pip install -r requirements.txt`
- Build-time commands: those pip commands only. They can run package install hooks. They do not import or start the bot.
- Network requirements: a successful build needs a base image and a package index. Both can require the network.
- COPY inventory: 59 package files, `requirements.txt` once, `main.py` once
- Entry point: `uvicorn forex_bot.app:app` on port 8000
- Exposed port: 8000
- Unsupported constructs: none in the repaired Dockerfile. There is no `USER` and no `ARG`. The image default user is root.

## 5. Supply-chain assessment

- Base-image pull possible: yes. Local presence was not checked.
- Dependency downloads possible: yes
- Dependency versions pinned: no. `requirements.txt` uses minimum ranges and no hashes.
- Build scripts: the pip install lines
- External network required: yes for this Dockerfile as written
- Offline build feasible: no, unless an unverified local base image and wheel cache already exist
- Reproducibility limitations: the tag and the version ranges can resolve differently on another day

## 6. Proposed build

- Exact command: not submitted for approval. The rejected repository-root example is in `proposed_build_plan.md`.
- Working directory: not approved
- Context path: the repository root is rejected
- Candidate tag: `forexttradingbot1st-g14-candidate:d080d89-4a458b4b` was considered and not created. `CANDIDATE_TAG_AVAILABILITY_UNVERIFIED`
- Pull policy: not approved. `--pull=false` would still be insufficient while the context contains the backups.
- Network policy: not approved. `--network=none` would fail at pip with the current Dockerfile.
- Cache policy: not approved
- Build arguments: none
- Expected disk usage: the measured context is 1,516,574 bytes. The base-image and wheel sizes are unknown.
- Running-production isolation: no command was run, so the running container, image, tag, mounts, and authorisation were not touched

## 7. Proposed image verification

- Metadata inspection: `docker image inspect` and `docker image history` of the candidate tag only, after a future approval
- Filesystem inspection: `docker image save` to a path outside OneDrive, then an offline tar read. No `docker run`, `docker create`, `docker exec`, or `docker cp`.
- Expected application files: 61
- Hash comparison: current allowlist hashes, not the historical Dockerfile hash
- Secret review: required before any future export is kept
- Output paths: none created
- Cleanup policy: no candidate exists. A future `docker image rm` of only the candidate tag would need its own approval. The running image must not be removed.

## 8. Tests

- Exact commands: recorded in `test_results.json`
- Tests passed: 277
- Tests failed: 0
- Tests skipped: 0
- Ruff: passed for `tests/test_g14_context.py`
- Mypy: no errors reported for that file
- Untested paths: daemon context behaviour, base-image presence, pip resolution, and any image filesystem

## 9. Remaining blockers

- Safety-state compatibility: `SAFETY_STATE_FORWARD_COMPATIBILITY_UNVERIFIED`
- Live database compatibility: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`
- Shadow-mount compatibility: `SHADOW_MOUNT_COMPATIBILITY_UNVERIFIED`
- Verified rollback target: `NO_VERIFIED_ROLLBACK_TARGET`. The running image stays `ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED`.
- Runtime validation: not started
- Deployment readiness: no

## 10. Files changed

- Production source: unchanged
- Dockerfile: unchanged
- `.dockerignore`: unchanged
- Compose: unchanged
- Tests: `tests/test_g14_context.py`
- G.14 artifacts: `data/research/adaptive_ensemble/g14/`
- Running production: unchanged

## 11. Final classification

`BUILD_CONTEXT_EXPOSURE_BLOCKED`

## 12. Exact approval request

No Phase 2 command is offered for approval.

Do not run a repository-root `docker build`. The two gitignored environment backups would be uploaded to the daemon. A later request has to name a context that cannot include them, and it has to ask separately before any base-image pull or pip download.
