# G.14.4 candidate packaging integration

The current 63-file staging directory remains the context for the current Dockerfile. Its digest remains `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`.

A locked build would need a new baseline:

- a locked requirements file
- a verified wheelhouse
- a wheelhouse manifest
- a candidate Dockerfile
- a new staging directory
- a new allowlist

None of those files was created. The wheelhouse was not copied into the 63-file directory. The production Dockerfile, `requirements.txt`, `.dockerignore`, and Compose were not edited.

The new baseline would need its own allowlist, inventory, hashes, independent staging check, secret-exclusion tests, COPY-source check, context-exposure review, and a separate build approval. The old manifest digest would not cover that context.
