# Dockerfile static audit

The file was read as text. Docker was not run.

- Line 2: `FROM python:3.12-slim-bookworm`. Mutable tag. No digest.
- Line 4: `WORKDIR /app`.
- Lines 6–10: Python and pip environment variables. No secrets.
- Line 12: `COPY requirements.txt`.
- Lines 13–14: `pip install --upgrade pip` and an unpinned `pip install -r requirements.txt`. This step needs a network index and does not check hashes.
- Lines 17–76: explicit `COPY` of 60 Python files plus `main.py` is included in that range, and `requirements.txt` is the earlier copy. Total `COPY` instructions: 61. Every listed source exists and none of those 61 paths is a symlink.
- Line 78: `EXPOSE 8000`.
- Line 81: `CMD ["uvicorn", "forex_bot.app:app", "--host", "0.0.0.0", "--port", "8000"]`.

There is no `USER`, so the image text assumes root. There is no `HEALTHCHECK`. There is no `ADD`. There are no build secrets or build arguments. `pip` is upgraded inside the image, so the installer itself is not pinned.

A static import walk from `forex_bot/app.py` and `main.py` stayed inside the copied files. That shows source completeness for the current import graph. It does not show that a build is reproducible.
