# Proposed image-forensics method

This plan is not approved and has not been executed.

## Method

1. `docker image save` of the exact image ID to one local tar.
2. A local Python reader opens that tar. It does not call Docker again.
3. The reader checks the save manifest, layer order, and layer blob hashes.
4. It merges layers in order and applies whiteout and opaque-directory rules.
5. It hashes only the safety-critical application paths from the merged result.
6. It records secret-like filenames and assignment names. It does not record values.
7. It deletes the save tar after the hash report is written.

Rejected methods: `docker create`, `docker run`, `docker exec`, `docker cp`, and any container start.

## Why history is not enough

`docker image history` shows `COPY forex_bot ./forex_bot` and `COPY main.py .` at `2026-10-08T22:24:01Z`. Those layer IDs are `<missing>`, so history cannot supply file hashes.

## Storage

`docker image inspect` reports `Size` `111899777` bytes. Reserve 250 MB for the save tar. Do not unpack the full image root. The earlier image listing showed about 483 MB unpacked, and that full unpack is unnecessary.

## Output

`data/research/adaptive_ensemble/g12/forensics/`

That directory is under `data/`, so it stays outside the frozen G.10 source snapshot. It will not be created until the operator approves the save.

## Secrets and deleted files

The running container's environment is not part of an image save. The image may still contain a copied env file if the 8 October build context included one. A later layer can hide a file without removing it from an earlier blob. Any such path will be reported with its layer index and no contents.

## Running container

Image save reads the image store. It does not write the container filesystem, change its restart policy, or stop it.
