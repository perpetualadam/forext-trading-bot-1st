# Resolution strategy

Resolution is not authorised in this stage.

Inputs must be the hashed `requirements.txt`, a verified Python 3.12 patch, a verified architecture, a verified libc and base-image digest, an approved resolver version, and an approved index policy. The host's installed packages are not an input.

The resolver runs in a disposable environment that matches that target, or through a cross-resolver whose platform flags have been proven in a later stage. It selects exact versions and one compatible wheel per distribution. If a distribution has no compatible wheel, resolution fails closed.

Output is the proposed lock schema plus a provenance template. A reviewer compares the lock with the input hashes before any download. Failure leaves no partial lock promoted into the Dockerfile.

pip-tools and uv can both be candidates because they can emit hashes. Neither was executed, and neither is assumed to be installed. Poetry is a poor fit: there is no `pyproject.toml`, and adopting it would change the image install path. Pins without hashes are not sufficient. The planning preference is one single-platform hashed requirements lock for the verified Linux target, consumed later by `pip install --require-hashes --no-index`. The tool name stays unverified until its version is pinned and its target flags are shown.
