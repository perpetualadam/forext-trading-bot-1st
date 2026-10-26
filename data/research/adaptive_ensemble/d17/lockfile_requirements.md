# Lockfile requirements

The future production lock is a schema only. It is not a resolved lock and it is not installable.

It must record exact direct versions, the full transitive closure, marker evaluation for one target, artifact file names, SHA-256 hashes, origin, resolver name and version, the hash of `requirements.txt`, a generation time, and a hash of the lock itself. Python, operating system, and architecture must be explicit. Development requirements stay out of the production lock.

No field was filled with a guessed version or a guessed hash.
