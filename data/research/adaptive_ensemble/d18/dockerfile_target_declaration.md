# Dockerfile target declaration

Evidence level for the lines below: `CURRENT_LOCAL_FILE_VERIFIED`. File hash matched the D.18 expected Dockerfile hash.

- Line 2: `FROM python:3.12-slim-bookworm`.
- Registry hostname: not written.
- Repository name: `python`.
- Tag: `3.12-slim-bookworm`.
- Digest: absent.
- Platform directive: absent.
- Python major/minor: 3.12, declared by the tag.
- Python patch: not specified.
- Linux indicator: the tag contains `bookworm`.
- Stage count: one. There is no build stage and no stage alias.
- Architecture-specific instructions: none.
- Package installation: lines 13–14 upgrade pip and install `requirements.txt` with `--prefer-binary`. No hash check and no apt packages.
- Entrypoint: no `ENTRYPOINT` instruction.
- Command: line 81, `uvicorn forex_bot.app:app --host 0.0.0.0 --port 8000`.
- Working directory: line 4, `/app`.
- User: no `USER` instruction.
- Health check: no `HEALTHCHECK` instruction.
- Exposed port: line 78, `8000`.

The tag does not pin a digest, an architecture, or a Python patch.
