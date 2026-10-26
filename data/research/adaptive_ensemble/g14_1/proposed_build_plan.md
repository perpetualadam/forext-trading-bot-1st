# G.14.1 proposed candidate-image build

This procedure is not authorised for execution in G.14.1. No Docker command was run.

## Context

- Context directory: `C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2`
- Dockerfile: the repaired file inside that directory
- Manifest digest: `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`
- File count: 63
- Total bytes: 617279
- Repository root: not the context
- Compose: not used
- Production `latest` tag: not used

## Command

```text
docker build --pull=false --progress=plain -f "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2\Dockerfile" -t forexttradingbot1st-g14-candidate:d080d89-4a458b4b "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2"
```

## Network access this command permits

The command requires network access on a cold build. It is not an offline build.

- Base-image pull: permitted when `python:3.12-slim-bookworm` is not already local. `--pull=false` does not keep Docker from fetching a missing tag, and the tag is mutable.
- Python package downloads: permitted. The Dockerfile runs `pip install --upgrade pip` and `pip install -r requirements.txt`.
- Package installation hooks: permitted, because pip may execute them.
- Build-cache use: permitted. The command does not disable the daemon cache, and the cache was not inspected.
- Registry push: not requested. The command has no `--push` and does not name a registry destination.

## Unverified before that later stage

- `CANDIDATE_TAG_AVAILABILITY_UNVERIFIED`
- `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`
- `BASE_IMAGE_DIGEST_UNVERIFIED`

## The command does not

- pass broker or database credentials
- mount live data
- start a container
- replace the running image
- use the repository root as context

## Staging directory cleanup

Do not delete the staging directory as part of the build. A later cleanup must first confirm the exact directory and the manifest digest above, then delete only the 63 manifest paths and that directory. Do not recursively delete the Temp parent.
