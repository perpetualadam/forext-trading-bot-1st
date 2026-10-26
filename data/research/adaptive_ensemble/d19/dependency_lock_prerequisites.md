# Dependency-lock prerequisites

No lock is created in D.19.

A future lock needs an explicit platform, an explicit registry choice, a verified base-image identity, a sufficiently defined Python target, an established ABI, established libc compatibility, a wheel policy, an approved resolver version, and an approved hash policy. None of those approvals is present.

The prohibited outputs remain `requirements.lock`, `requirements-pinned.txt`, `constraints.txt`, `uv.lock`, `poetry.lock`, `Pipfile.lock`, and any other resolved lock.
