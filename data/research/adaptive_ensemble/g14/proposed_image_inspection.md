# Proposed image inspection

No image was built. These commands are not approved and were not run.

If a later stage produces a candidate, inspection must not start the application.

Allowed shapes, after a separate approval and only for the candidate tag:

- `docker image inspect forexttradingbot1st-g14-candidate:d080d89-4a458b4b`
- `docker image history forexttradingbot1st-g14-candidate:d080d89-4a458b4b`
- `docker image save` of that exact tag to a directory outside OneDrive, followed by an offline tar read

Not allowed:

- `docker run`
- `docker create`
- `docker exec`
- `docker cp`
- starting Uvicorn or the FastAPI lifespan

The offline read would compare the 61 application files under `/app` with the current allowlist hashes. `Dockerfile` and `.dockerignore` are not expected in `/app`. System files and installed site-packages are not application files. The comparison must use the current Dockerfile hash `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`, not the historical G.10 Dockerfile hash.

Any export would be treated as sensitive. Its path, hash, and deletion command would need their own approval. No export path was created.

Cleanup of a future candidate tag would be `docker image rm` of that tag only, and only after a separate approval. The running image `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25` must not be removed.
