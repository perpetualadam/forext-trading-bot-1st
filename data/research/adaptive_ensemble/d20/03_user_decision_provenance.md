# User decision provenance

The D.20 instruction states two explicit decisions.

- Approved intended platform: `linux/amd64`.
- Approved proposed base-image reference: `docker.io/library/python:3.12-slim-bookworm`.
- Proposed additional platform: `linux/arm64`.
- Multi-platform policy `linux/amd64 + linux/arm64`: not explicitly approved.
- Future VPS provider: not selected.
- Future VPS hardware: not verified.
- Current production architecture: not verified.

D.19 recorded `selected_platform: null` because that stage's instruction forbade treating stage execution as approval. That D.19 file is unchanged. The newer decision text is the D.20 instruction. A historical G.14.2 `linux/amd64` note remains a local Docker Desktop observation and is not this approval.

Approval of the image reference is not approval of a digest. Approval of `linux/amd64` is not proof that a future VPS is x86-64. Interest in portability is not approval of `linux/arm64`. No live-trading approval exists.
