# D.25 NEXT STAGE DECISION RECORD

D.25 recommends Option C, controlled platform-specific dependency metadata verification, as the next evidence stage. This record does not authorise that stage.

## COMPARISON

Further offline analysis has now covered the preserved OCI bytes, Dockerfile, Compose, and requirement declarations. Another offline pass would not create wheel filenames, artifact hashes, an ABI measurement, or a libc version.

Controlled image-layer metadata would address installed Debian packages, libc files, and interpreter files inside the verified base image. It needs new registry or storage access and may download layer blobs. It does not select application wheels.

Controlled dependency metadata would address the shared blocker in `requirements.txt`: nine lower-bound requirements, no hashes, and no per-platform wheel records. It can be limited to a named package index, with separate linux/amd64 and linux/arm64 records, without Docker and without image layers.

## WHY OPTION C COMES FIRST

The Dockerfile's dependency step is an unpinned pip install. That gap applies to both intended architectures and can be narrowed without pulling image layers or running a container. Option C is less invasive than layer retrieval and more informative than another offline review.

Option C does not establish a measured interpreter, SOABI, libc version, VPS compatibility, image signature, bot startup, or rollback artifact. Any wheel tag used in that future stage remains an explicit assumption until Option B or Option E measures the image.

## APPROVAL REQUIRED BEFORE OPTION C

A later approval would need to name the package index, the exact platform tags, the request budget, and a prohibition on installation, lockfile generation, image builds, and production access. D.25 does not grant that approval.

## ALTERNATIVE

If the next priority is the base-image filesystem rather than package metadata, Option B is the alternative. It requires its own host allowlist and blob scope. D.25 does not start Option B.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
