# Future registry access boundary

Approval of `docker.io/library/python:3.12-slim-bookworm` does not authorise a network request.

A later registry stage must name the hostname `docker.io`, the repository `library/python`, the reference, the OCI platforms that were actually approved, the destination, the methods, timeouts, maximum response size, redirect policy, authentication policy, evidence path, digest checks, and stop conditions. Authentication must not use broker or Telegram secrets. Layers must not be downloaded. Docker must not run.

If the response does not contain the selected platform, that platform stays unverified. This stage made no registry request.
