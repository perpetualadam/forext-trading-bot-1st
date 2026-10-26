# Filesystem guard review

`_blocked_path` denies a basename of `.env` or ending in `.env`, and paths containing `data/ops`, `v2_shadow`, `credential`, or `pgdata`.

Wrapped operations:

- `builtins.open`
- `pathlib.Path.open`
- `os.open`
- `os.replace`
- `os.rename`
- `os.remove`
- `os.unlink`
- `shutil.move`
- `shutil.copy`
- `shutil.copy2`
- `shutil.rmtree`

The self-check opens denied paths through the guarded `open`. Temporary safety state and the child work directory remain writable.

`shutil.copyfile` and `shutil.copytree` are not separately wrapped. The D.13 lifespan paths did not need them. Guards were not weakened.
