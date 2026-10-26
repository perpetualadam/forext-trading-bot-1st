# Historical platform evidence

G.14.2 recorded a Docker Desktop daemon and a local base image as `linux/amd64`. The local base-image ID in that report and in D.16 is `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`. G.14.2 repeated that same hex without a registry hostname. G.14.5 and D.16 left the registry digest unverified. D.18 recorded those notes and did not select a platform.

No reviewed historical file selects `linux/arm64` as the future deployment target. No historical file is a current user approval. The local image ID is not a registry digest. Docker was not inspected to add evidence.
