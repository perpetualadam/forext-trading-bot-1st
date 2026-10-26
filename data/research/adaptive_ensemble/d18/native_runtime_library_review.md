# Native runtime libraries

`forex_bot/database.py` imports `psycopg2` and connects with it. The declared distribution is `psycopg2-binary`. Whether that wheel carries its own client library, and which OpenSSL it expects, is unverified. The server image `postgres:16-alpine` is not the client runtime.

`requests` is declared and imported. TLS and CA behaviour depend on undeclared transitive packages and on whatever certificates are in the base image. Those versions were not read.

libc is an inferred glibc with no version. Numeric extensions in numpy and pandas need that libc and the selected CPU architecture. Compiler runtime libraries are not installed by the Dockerfile and were not inventoried.

`zoneinfo` is imported by `forex_bot/session_rules.py`, which is in the image copy list. Compose declares `TZ` with a non-secret default of `Europe/London`. The pip package `tzdata` is declared. The base-image timezone package list is unknown.

Filesystem mounts declare two host paths. The image user that would write them is unknown. No `ldd`, apt, or container inspection was run. No exact installed library version is asserted.
