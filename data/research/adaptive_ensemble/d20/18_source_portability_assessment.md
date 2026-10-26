# Source portability

`SOURCE_PORTABILITY_CANDIDATE`: the Dockerfile, Compose file, requirements, and application copy set contain no `amd64` or `arm64` strings. The same source could be copied into two images. That is not a guarantee.

`DEPENDENCY_PORTABILITY_UNVERIFIED`: numpy, pandas, psycopg2-binary, and the uvicorn standard extra need per-architecture artifacts that were not obtained.

`RUNTIME_PORTABILITY_UNVERIFIED`: Python patch, ABI, and libc are unknown on both platforms.

`IMAGE_PORTABILITY_UNVERIFIED`: one tag does not prove the registry index lists both platforms.

`OPERATIONAL_PORTABILITY_UNVERIFIED`: no VPS, mount rights, or runtime test exists for either architecture.

`forex_bot/research/adaptive_ensemble/g10_snapshot.py` and `g10_audit.py` call `ctypes.windll.kernel32`. Those files are not in the Dockerfile `COPY` list. They were not changed, and they are not evidence that the bot image is portable. No architecture detection was added.
