# Transitive native risks

No dependency closure was resolved.

- Numeric libraries: `DIRECTLY_DECLARED` through numpy.
- Dataframe libraries: `DIRECTLY_DECLARED` through pandas, which commonly depends on numpy. The exact pandas dependency set is `UNVERIFIED`.
- PostgreSQL adapters: `DIRECTLY_DECLARED` as `psycopg2-binary`. The import in `forex_bot/database.py` is `psycopg2`.
- Event-loop accelerators: `POSSIBLE_TRANSITIVE` from the `uvicorn[standard]` extra. The extra's current dependency list was not read from an index.
- HTTP parsing accelerators: `POSSIBLE_TRANSITIVE` from that same extra.
- YAML extensions: no YAML import was established for the image copy set. `NOT_APPLICABLE` as a direct image requirement.
- Cryptographic libraries and CA bundles: `POSSIBLE_TRANSITIVE` through `requests`. Exact packages are `UNVERIFIED`.
- Compression libraries: `POSSIBLE_TRANSITIVE`. Not asserted as present.
- Runtime C libraries: glibc is an inference for the bot image. Version `UNVERIFIED`.

A future lock is required before any of the possible transitive rows become a real closure.
