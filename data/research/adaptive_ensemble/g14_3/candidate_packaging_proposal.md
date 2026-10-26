# G.14.3 candidate packaging proposal

Nothing in this proposal was created. The production Dockerfile, `requirements.txt`, and application sources stay as they are.

## Future files, after evidence exists

- A locked requirements file with exact versions and SHA-256 hashes. Versions are `UNKNOWN` now, so the file must not be written yet.
- A dependency-artifact manifest.
- A verified wheelhouse outside OneDrive and outside the current staging directory.
- A candidate-specific Dockerfile, separate from the production Dockerfile.
- A base-image identity manifest. It may record the historical local image ID. It must not claim a registry digest.
- A build script and a post-build checker. Both stay unexecuted until their own approvals.

## Candidate Dockerfile differences

The candidate file would not be equivalent to the verified G.13 Dockerfile and would need its own review.

Retain:

- `WORKDIR /app`
- the same 61 explicit `COPY` lines for the application files
- `CMD ["uvicorn", "forex_bot.app:app", "--host", "0.0.0.0", "--port", "8000"]`
- no application import and no lifespan execution during the build
- no credentials, operational state, research trees, tests, or backup files

Change only in the candidate file:

- Do not run `pip install --upgrade pip` unless a reviewed pip wheel and hash exist. That version is `UNKNOWN`.
- Install with `--no-index`, `--only-binary=:all:`, and `--require-hashes` from the wheelhouse.
- Copy the lock file and wheelhouse as explicit inputs. No wildcard and no `COPY . .`.
- Leave `FROM` unpinned until a real registry digest exists. Do not write the image ID into `FROM` and call it a registry digest.

The production file keeps `FROM python:3.12-slim-bookworm` and the unpinned pip upgrade.

## Entrypoint and authorisation

The candidate image would still start through the existing fail-closed lifespan. This proposal does not change live-order authorisation and does not activate a strategy.
