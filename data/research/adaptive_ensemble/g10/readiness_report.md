# Stage G.10 readiness

Classification: `SOURCE_SNAPSHOT_VERIFIED_ALLOWLIST_READY_REVIEW_REQUIRED`

Snapshot `stage_g10_consolidated_source_v1` is frozen. Archive SHA-256 `d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277`. Manifest SHA-256 `93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf`. 196 files, 1,502,270 payload bytes, USTAR. Two temporary archives matched, and an independent reader verified the official archive. Tests did not rewrite it.

The proposed production allowlist has 63 files. It keeps the safety modules and excludes research source. It is not applied. The Dockerfile still copies `forex_bot/` and was not edited. No image was built and no deployment is authorised.

Unverified: running image identity, rollback identity, Docker daemon context rules, live database compatibility, runtime configuration, full repository suite, and operator approval.
