# G.14.3 pip toolchain review

The production Dockerfile contains:

```text
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefer-binary --timeout 120 --retries 15 -r requirements.txt
```

`PIP_DISABLE_PIP_VERSION_CHECK=1` only suppresses pip's version check. It does not pin pip.

## Consequences

1. The pip version can change whenever the index publishes a newer pip.
2. Resolver behavior can change with that pip version.
3. The upgrade contacts a package index.
4. A network failure or a different index response changes the build.
5. A later rebuild cannot be shown to use the same pip unless the version and wheel hash were recorded.

## Known version

No evidence in G.14.2 records the pip version inside `python:3.12-slim-bookworm`. This stage did not start a container and did not inspect the image.

Classification: `PIP_TOOLCHAIN_VERSION_UNVERIFIED`

## Proposed change

Do not edit the production Dockerfile.

In a future candidate-specific Dockerfile, remove the unpinned upgrade. Keep the base-image pip only after its version and wheel identity are recorded, or install one reviewed pip wheel by hash. Until one of those artifacts exists, the candidate file must not claim a pip pin.

`--no-cache` does not pin pip. `--pull=false` does not pin pip.
