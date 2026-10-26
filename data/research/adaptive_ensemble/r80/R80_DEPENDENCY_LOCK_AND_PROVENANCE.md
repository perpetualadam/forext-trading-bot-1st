# R.80 dependency lock and provenance

`DEPENDENCY_RESOLUTION_RECORDED`: PASS.
`HASH_LOCKFILE_CREATED`: PASS.
`CLEAN_REINSTALL_VERIFIED`: NOT_VERIFIED.

The lock is `R80_LINUX_REQUIREMENTS_LOCK.txt`. It was transcribed from `$HOME/r79-pip-report.json`. That report lists 31 install entries. Each SHA-256 is the hash pip recorded for the downloaded artifact. Installed-package directories were not hashed.

Interpreter recorded with the resolution: CPython 3.12.3 on WSL2 Linux x86_64. The disposable environment is `$HOME/r79-disposable-venv`. It was reused. No package was installed, upgraded, or removed. `requirements.txt` was not edited.

`oandapyV20` 0.7.2 is a source distribution. The other 30 artifacts are wheels. Several wheels are CPython 3.12 manylinux x86_64 artifacts and are not Windows packages. `uvloop` does not run on Windows.

A later resolution of the minimum-version `requirements.txt` can select different versions. This lock is not claimed to be reproducible until a clean reinstall is authorised and succeeds. That reinstall was not performed.
