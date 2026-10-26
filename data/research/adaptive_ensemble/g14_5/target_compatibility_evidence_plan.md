# Target compatibility evidence plan

Known from existing design records, not from a new runtime probe:

- Operating system: Linux.
- Architecture: x86_64 / AMD64.
- Interpreter family: CPython.
- Python major and minor: 3.12.

Unknown, and not invented here:

- Python patch version.
- SOABI.
- glibc version.
- pip version inside the base image.
- exact supported native wheel tags.
- registry manifest digest.

Evidence classes:

- A. Existing local reports supply the intended platform and the historical local image ID. They do not supply the unknown values above.
- B. Source files supply the mutable tag `python:3.12-slim-bookworm` and the unpinned requirements. They do not supply the interpreter patch or glibc.
- C. A later read-only Docker metadata query could confirm the local image identity. It was not run in this stage.
- D. Offline inspection of an exported image could show file paths and library filenames. An export was not created. Filenames alone may not prove the interpreter patch, pip version, or every accepted wheel tag.
- E. An isolated interpreter probe could print the patch version, SOABI, glibc, and pip version. That probe needs its own approval. It must not mount production volumes or contact OANDA, and it must not start the trading application.

These methods are not interchangeable. Classification: `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`.
