# Python ABI requirements

`GENERAL_PACKAGING_KNOWLEDGE`. CPython 3.12 native extensions normally use a `cp312` ABI tag. `abi3` wheels can target a stable ABI across newer CPython versions when the publisher built them that way. `py3-none-any` wheels are pure Python and are not tied to one ABI or CPU. A patch release can still matter when a wheel's `Requires-Python` range excludes it.

`PROJECT_LOCAL_EVIDENCE`. The Dockerfile tag declares Python 3.12. It does not declare CPython, an ABI tag, or a patch.

`FUTURE_VERIFICATION_REQUIRED`. The accepted tags inside the eventual container are not known. A 3.12 declaration does not list them. No exact tag list was created.
