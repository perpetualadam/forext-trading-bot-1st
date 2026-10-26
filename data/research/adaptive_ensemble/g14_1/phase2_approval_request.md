# G.14.1 approval request — candidate image build

Approval is requested for a later stage. This request does not authorise execution now.

## Requested command

```text
docker build --pull=false --progress=plain -f "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2\Dockerfile" -t forexttradingbot1st-g14-candidate:d080d89-4a458b4b "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2"
```

## Explicit network permission required

The build is `NETWORK_REQUIRED`.

Please authorise, or refuse, all of the following:

1. A pull of `python:3.12-slim-bookworm` if that mutable tag is not already present locally.
2. Downloads from the Python package index for the unpinned requirements and for the pip upgrade.
3. Execution of package installation hooks during `pip install`.
4. Use of the local Docker build cache. Its contents were not inspected.
5. No push to a registry.

Do not treat this build as offline. `--pull=false` only avoids a refresh when a local tag already exists.

## Bounds

- Context: the staging directory above, never the repository root.
- Tag: `forexttradingbot1st-g14-candidate:d080d89-4a458b4b`. Availability is `CANDIDATE_TAG_AVAILABILITY_UNVERIFIED` and must be checked before the build.
- No Compose.
- No production `latest` tag.
- No credentials, live mounts, container start, or replacement of `forexttradingbot1st-bot-1`.
- Docker daemon context behaviour remains `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED` until that build is observed.
- Building this image would not authorise deployment or a change to live-order authorisation.

## Not requested

- Reading the two environment backup files.
- Deleting the staging directory.
- Changing the Dockerfile, `.dockerignore`, or the G.10 allowlist.
