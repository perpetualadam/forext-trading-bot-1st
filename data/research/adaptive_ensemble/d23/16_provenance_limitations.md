# Provenance limitations

- OCI digest verification establishes byte identity relative to the trusted local references and the historical registry digest preserved by D.22-R1.
- OCI digest verification does not by itself establish publisher authenticity.
- The mutable tag `python:3.12-slim-bookworm` may later resolve to different content. D.23 did not resolve the tag again.
- The AMD64 and ARM64 manifests have different config digests and different layer descriptors.
- The index contains attestation descriptors. They were not retrieved and their signatures were not validated.
- Registry transport security is not equivalent to supply-chain provenance.
- A config digest is a reference inside a verified manifest. It is not a verified rollback artifact.
- This planning stage does not approve production deployment.

Manifest digest equality does not declare the base image secure.
