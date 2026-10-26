# G.14.4 proposed acquisition commands

These are templates. They are not approved commands. They were not run.

Unresolved values:

- `<UNRESOLVED_APPROVED_INDEX>` because `PACKAGE_SOURCE_APPROVAL_REQUIRED`
- `<UNRESOLVED_WHEELHOUSE>` because the directory must not be created in Gate A
- `<UNRESOLVED_PLATFORM_TAG>` because glibc and the exact manylinux tag are `UNKNOWN`
- `<UNRESOLVED_ABI>` because the base-image SOABI is `UNKNOWN`
- `<UNRESOLVED_PIP>` because `PIP_TOOLCHAIN_VERSION_UNVERIFIED`

Do not fill those placeholders in from the Windows host.

## Template, not for execution

```text
python -m pip download --only-binary=:all: --implementation cp --python-version 3.12 --platform <UNRESOLVED_PLATFORM_TAG> --abi <UNRESOLVED_ABI> --dest <UNRESOLVED_WHEELHOUSE> --index-url <UNRESOLVED_APPROVED_INDEX> --requirement requirements.txt
```

`--no-deps` is omitted on purpose. The transitive graph is `UNKNOWN`, so dropping dependencies would be an incomplete lock.

`--only-binary=:all:` is required. A source fallback is a stop, not a retry.

The flag spellings above depend on the pip version. That version is `UNKNOWN`, so the template is not finalized.

## What this template does not settle

A cross-platform download can select tags without evaluating every environment marker the way an install on linux/amd64 would. If that gap cannot be shown to be closed, the download stops and a later approval would be required for an isolated target resolver. Creating or running that resolver is not part of Gate A.

Forbidden until their own approvals: `pip install`, `pip wheel`, `pip index`, execution of setup scripts, and execution of downloaded files.
