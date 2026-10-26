# Build-context risk review

Compose builds with `build: .`, so a future build context is the repository root after `.dockerignore`. The Dockerfile then copies an explicit list.

Secret inclusion: `.env` is ignored and was not read. Compose and `forex_bot/config.py` contain fallback database password literals. Those literals were not copied into this report. Production values were not read.

Runtime state: `/data` is ignored, so the context upload should not include operational or shadow state. The image can still see that state through compose mounts.

Research artifacts under `data/` are ignored. Tests are ignored. The Dockerfile does not copy them.

Dirty files: `Dockerfile` and the five protected application files are modified in the working tree. A future build would copy those working-tree bytes, not the bytes stored at Git HEAD. HEAD alone is not the source identity.

The 61 copy sources are not symlinks. OneDrive residency of the workspace can still change file timing and was not proven deterministic. No context archive was created.
