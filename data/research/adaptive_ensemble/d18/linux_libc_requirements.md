# Linux distribution and libc

The Dockerfile tag contains `bookworm`. That supports an inference that the intended family is Debian and the release codename is bookworm. Evidence level: `STATIC_INFERENCE`. The image's OS release file was not read.

glibc is the usual libc for Debian. musl is the usual libc for Alpine. The bot image tag is not Alpine. The Compose database image is `postgres:16-alpine`, which is a different service and must not be used as the bot libc. Evidence level for bot glibc: `STATIC_INFERENCE`. The version is `MISSING`. The word bookworm does not supply a glibc version.

No apt packages are installed by the Dockerfile. OpenSSL, CA certificates, libpq, and timezone files inside the base image were not inspected. `tzdata` is a Python requirement. `forex_bot/session_rules.py` imports `zoneinfo`. Whether the slim image or the pip package supplies zone data is unverified.
