# Policy and configuration

The approved intended policy is `linux/amd64` plus `linux/arm64`. The current Dockerfile line 2 is `FROM python:3.12-slim-bookworm`. It names no registry hostname, no digest, and no platform. The Compose bot service builds `.` and names no platform, image, command, restart policy, or health check.

The policy is not represented in either file. Both files are architecture-neutral in the limited sense that they do not pin one OCI platform. They are not a multi-platform build definition. Adding an explicit platform field would restrict a build to that one architecture. A future image for each approved platform would need its own build input. A future VPS would then need the image that matches its hardware. None of those inputs were added.

Dockerfile and Compose were not modified.
