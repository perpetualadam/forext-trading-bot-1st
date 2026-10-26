# dockerignore static audit

`.dockerignore` excludes `.git`, virtual environments, caches, `.env`, `.env.*`, with an exception that re-includes `.env.example`, key and certificate name patterns, `/data`, databases, logs, archives, editor directories, markdown, `/tests`, `/reports`, and `docker-compose.yml`.

`.env` is present and was not read. The ignore rule excludes it from a future context upload. `.env.example` is present, was not read, and the exception would allow it into an upload. The Dockerfile does not copy it into the image.

`/data` is excluded, so operational and shadow files are not part of the context upload. Compose still bind-mounts those paths at runtime. The ignore file does not remove those mounts.

The current `.dockerignore` hash matches the G.10 allowlist record. The Dockerfile hash does not.
