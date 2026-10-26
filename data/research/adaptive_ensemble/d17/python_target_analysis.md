# Python target analysis

Dockerfile line 2 says `FROM python:3.12-slim-bookworm`.

- Major version: 3, declared by the tag.
- Minor version: 12, declared by the tag.
- Patch version: not declared.
- Digest: not declared.
- Implementation: the official image name implies CPython. That was not verified by inspecting an image.
- ABI: not specified.
- Architecture: not specified.
- Operating-system identity: the tag names Debian bookworm. The exact image revision is not fixed.

A mutable tag does not identify one Python patch release or one set of image bytes. The historical local image id was not reused as a digest.
