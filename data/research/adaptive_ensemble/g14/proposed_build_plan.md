# Proposed build plan

This plan is not approved and was not executed.

## Why a repository-root build is blocked

A build whose context is the repository root would send the Docker daemon every file left in by `.dockerignore`. The local matcher, which is not the daemon, includes two gitignored environment backups:

- `main example .env backup.txt` (7922 bytes)
- `# Copy to .env and fill in. docker.txt` (7280 bytes)

Their contents were not read. `.dockerignore` excludes `.env` and does not exclude these names. The explicit `COPY` list would not put them in the image, but the daemon would still receive them.

The same context also includes 123 research Python files and deploy/scripts that the Dockerfile does not copy. Research datasets under `data/` are excluded.

Classification: `BUILD_CONTEXT_EXPOSURE_BLOCKED`.

## What was not created

No staging directory was created. No image tag was created. Tag availability is `CANDIDATE_TAG_AVAILABILITY_UNVERIFIED`.

A later minimal context, if separately designed, would contain only:

- `Dockerfile`
- `requirements.txt`
- `main.py`
- the 59 allowlisted `forex_bot` modules

It would not contain the two backup files, `.env`, `data/`, tests, or research modules. The Dockerfile's `COPY` paths are relative to that context and match those paths. That staging directory was not populated.

## Supply chain, unchanged by staging

`FROM python:3.12-slim-bookworm` is a mutable tag. Its digest is unknown. `RUN pip install` uses minimum version ranges and can download packages and run their install hooks. An offline build is not feasible with this Dockerfile unless a base image and a wheel cache are already present. Phase 1 could not check that without Docker commands.

Network access is not requested. Context exposure already blocks Phase 2.

## Command that must not be run

This command is recorded so the rejected repository-root build is explicit. It is not an approval request. It would upload the blocked files and would also need network for `pip`.

```text
docker build --pull=false --network=none -f Dockerfile -t forexttradingbot1st-g14-candidate:d080d89-4a458b4b .
```

Working directory would have been the repository root. That context is rejected. Do not add `--network=host` or omit `--network=none` as a workaround. Do not use the tag `forexttradingbot1st-bot:latest`.
