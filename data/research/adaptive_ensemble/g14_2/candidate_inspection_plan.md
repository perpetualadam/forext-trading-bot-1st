# G.14.2 candidate-image inspection plan

Do not execute this plan in G.14.2. It applies only after a separately approved build produces `forexttradingbot1st-g14-candidate:d080d89-4a458b4b`.

## Permitted later methods

- `docker image inspect` of that candidate tag only, using field formats that omit environment values.
- `docker image history` of that candidate tag only.
- `docker image save` of that candidate image only, to a new directory outside OneDrive.
- Offline reading of that new archive.

## Prohibited during inspection

- `docker run`
- `docker create`
- `docker exec`
- `docker cp`
- Starting the candidate application or the FastAPI lifespan
- Replacing or removing the running image `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`
- Recreating `C:\Users\Brian\AppData\Local\Temp\forex-bot-g12-forensics\image_save.tar`

## Checks

1. Record the candidate image ID.
2. Record the image configuration digest.
3. Record image history, including the base layer identity.
4. Compare the base layer with local image `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`.
5. Inventory final `/app` files from the archive.
6. Compare SHA-256 of the 61 expected application files: 59 package files, `main.py`, and `requirements.txt`.
7. Reject unexpected application files.
8. Reject credentials, operational-state files, research trees, and the two environment-backup filenames.
9. Confirm the command remains `uvicorn forex_bot.app:app` on port 8000.
10. Record installed distributions only from image metadata or a layer listing. Do not run the application to ask pip.
11. Record layer provenance from history and the archive.
12. Confirm the running production image ID is still `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`.

## Export

- Proposed directory, not created now: `C:\Users\Brian\AppData\Local\Temp\forext-g14-2-candidate\`
- That path is outside OneDrive.
- C: had 169.65 GB free at preflight. The archive size is unknown until the image exists.
- Treat the archive as potentially sensitive.
- Record its size and SHA-256 after export.
- Deletion requires a separate approval. Do not delete it in the inspection stage that creates it.
