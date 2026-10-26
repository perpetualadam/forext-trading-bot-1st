# Dependency lock review

`requirements.txt` declares nine direct packages. Every constraint is a lower bound. `uvicorn` requests the `standard` extra. There are no environment markers, version-control URLs, or exact pins.

`requirements-dev.txt` includes `requirements.txt`, a lower bound on `packaging`, and a bounded range for `pytest`. That range does not pin the production install.

No `poetry.lock`, `Pipfile.lock`, `uv.lock`, `constraints.txt`, or other lockfile was found in the project. No file records a transitive graph, platform tag, or package hash.

Exact direct versions, exact transitive versions, and offline verification are missing. A lower bound does not make an installation reproducible.
