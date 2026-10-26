# Future target verification

These facts are blockers. They were not guessed and Docker was not inspected.

- Intended CPU architecture.
- Python 3.12 patch release inside the chosen image.
- Base-image registry digest.
- Debian bookworm image revision.
- glibc version.
- Native libraries required by the selected wheels.
- Accepted wheel tags.
- Trusted package index.
- Approved resolver and its version.
- Permitted artifact types. The planning preference is wheels only.

A later stage may read a registry digest and a published image config under its own network approval. It must not pull the image into a production daemon, build the bot, or contact the broker.
