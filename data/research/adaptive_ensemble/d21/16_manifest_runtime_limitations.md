# Manifest limits

An index digest and two platform manifest digests identify image documents. They do not establish the Python patch, the ABI, the libc version, the Debian revision, installed native libraries, application dependency compatibility, the runtime user, health behaviour, or trading-bot safety behaviour.

The tag `3.12-slim-bookworm` does not supply those facts. A later configuration or runtime metadata inspection needs its own approval. No container is run for that purpose in this stage.
