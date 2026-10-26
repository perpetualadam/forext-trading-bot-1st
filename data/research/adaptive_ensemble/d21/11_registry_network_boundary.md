# Registry network boundary

Nothing in this section is an approved destination.

- Proposed registry hostname: `docker.io`.
- Proposed repository: `library/python`.
- Proposed reference: `docker.io/library/python:3.12-slim-bookworm`.
- Proposed authentication: anonymous only if a later approval finds that the registry allows it. Any unexpected credential demand stops the stage.
- Proposed methods: `GET` for a manifest document. No blob `GET`.
- Proposed API shape, as general registry knowledge and not a verified endpoint: a version 2 manifest path for `library/python` and the tag `3.12-slim-bookworm`. The concrete host, such as a registry API hostname, must be named in the later approval. It is not approved now.
- Proposed content types: an OCI index and a Docker manifest list. Other types stop the stage.
- Proposed timeout: 30 seconds, not approved.
- Proposed maximum response size: 1 MiB for the index and 1 MiB for each platform manifest. Layers are out of scope.
- Proposed redirect policy: stop on any redirect whose host was not named in the approval.
- Proposed retry policy: no retry for digest, authentication, TLS, size, or schema failures. A later approval may allow one retry for a rate limit or a server error.
- Proposed TLS rule: verify the server certificate. Do not disable verification.
- Proposed credentials: none stored and none requested.
- Proposed evidence storage: a new research directory named by that later stage.
- Proposed stop conditions: the F01–F20 list.

No DNS lookup, HTTP request, token request, or Docker manifest command was run.
