# Future runtime evidence plan

No class B, C, D, or E evidence is collected in D.23. Class A is available only after a separately approved config-blob verification. A class A field does not prove a later class.

## Properties

- Python implementation.
- Python patch version.
- Python ABI.
- Python executable location.
- Python runtime build properties.
- Debian release.
- Debian package revision.
- libc family.
- libc version.
- Relevant native shared libraries.
- Platform-specific compatibility, separately for linux/amd64 and linux/arm64 variant v8.

## Evidence classes

A. Image configuration JSON. Possible fields include architecture, variant, os, config.User, config.Env, config.Cmd, config.Entrypoint, config.WorkingDir, and labels. Record a field only when it is present. Do not treat a version label as a measured interpreter.

B. Image filesystem or package metadata. This includes the Python executable, Debian release files, package status, and shared-library names. It requires layer access or an equivalent offline filesystem snapshot under a future approval.

C. Isolated runtime execution. This includes running the interpreter to report implementation, version, and ABI. It requires a container or an equivalent isolated execution approval. D.23 does not authorise it.

D. Dependency artifacts. This includes wheel tags, hashes, and native-library linkage for the selected Python ABI and architecture. It requires a later dependency stage.

E. Actual VPS hardware. This includes the production machine architecture and operating system. It requires a separate production-inspection approval. Current production state remains unverified.

## Boundary

The preserved manifests prove index and platform-manifest byte identity and the config descriptor references. They leave implementation, patch measurement, ABI, libc, wheels, and VPS compatibility for later classes.
