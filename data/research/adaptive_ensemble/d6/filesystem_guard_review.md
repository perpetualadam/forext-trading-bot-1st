# Stage D.6 filesystem guard review

## D.5 runner

`builtins.open` denies `.env`, `data/ops`, `v2_shadow`, and credential basenames. `pathlib.Path.open` and `Path.write_text` use `builtins.open`, so those are covered. `os.replace` is not covered. That is the gap recorded in the D.5 review.

## D.6 runner

The same open denial remains. Additional wrappers deny the same paths for `os.open`, `os.replace`, `os.rename`, `os.remove`, `os.unlink`, `shutil.move`, `shutil.copy2`, and `shutil.rmtree`.

The probes used a temporary directory whose path contained `data/ops` or the basename `.env`. They did not use the production safety file. The denied open and `os.replace` raised `PermissionError` before creating those files.

`LIVE_SAFETY_STATE_PATH` is set to a file in that temporary directory before import and before `initialise_fail_closed`. Successful safety writes stayed on that file. Every case left the file's authorisation field as `BLOCKED`.

`D6_FILESYSTEM_ISOLATION_BLOCKED` was not used for the D.6 harness.
