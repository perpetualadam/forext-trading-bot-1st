# G.14.2 revised candidate-build proposal

This command is not authorised for execution in G.14.2. It was not run.

## Command

```text
docker build --pull=false --progress=plain -f "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2\Dockerfile" -t forexttradingbot1st-g14-candidate:d080d89-4a458b4b "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2"
```

## Why this command still fits the preflight

- Context is the verified staging directory, not the repository root.
- The candidate tag was absent at preflight: `CANDIDATE_TAG_AVAILABLE_AT_PREFLIGHT`.
- `python:3.12-slim-bookworm` is present locally as image `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`.
- `--pull=false` uses that local tag when it is still present. It does not refresh it.
- The Dockerfile was not changed. It still says `FROM python:3.12-slim-bookworm`, so the tag is mutable.
- The RepoDigests field repeats that same image ID under the name `python`. That is not a separate registry manifest digest, so the Dockerfile is not being rewritten to pin it.

## Required check immediately before execution

Re-run only:

```text
docker image inspect python:3.12-slim-bookworm --format "{{.Id}}"
docker image inspect forexttradingbot1st-g14-candidate:d080d89-4a458b4b --format "{{.Id}}"
```

Abort if the base image ID is not `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`.
Abort if the candidate tag exists.
Do not pull, retag, or delete an image to make the check pass.

## Policies

- Pull policy: do not pull. If the local base tag is missing or its ID differs, stop.
- Network policy: network remains enabled. This is `NETWORK_REQUIRED` because `pip install --upgrade pip` and `pip install -r requirements.txt` download unpinned packages. `--network=none` is not feasible. No wheelhouse exists.
- Cache policy: the default build cache stays enabled. About 27.36 GB of build cache is already present. A cache hit can reuse an earlier unpinned install and does not make the result reproducible.
- Credentials passed: none.
- Package hooks: pip may execute third-party installation hooks.
- Running production: the command does not start, stop, or replace `forexttradingbot1st-bot-1`. The candidate tag is not the running image tag.
- Daemon context behaviour remains `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED` until a build is actually observed.

## Not part of this proposal

- Changing the Dockerfile or `requirements.txt`.
- Pinning a guessed digest.
- Pushing an image.
- Starting the candidate container.
- Pruning cache or images.
