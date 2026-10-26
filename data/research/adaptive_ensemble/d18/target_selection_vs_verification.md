# Target selection and target verification

Target selection defines the environment that is intended. Target verification independently establishes the identity and properties of that environment.

Selecting `linux/amd64` would not prove that a production host uses that architecture. Selecting the Python 3.12 tag does not prove a patch release. Selecting the repository `python` does not prove a registry digest. Selecting a wheel-only policy does not prove that compatible wheels exist.

The current files do not contain a platform selection. Historical `linux/amd64` text describes a past local image and a past Docker Desktop daemon. Using it as the future target would be a new decision. D.18 does not make that decision. A later selection needs explicit user approval because it would constrain deployment.
