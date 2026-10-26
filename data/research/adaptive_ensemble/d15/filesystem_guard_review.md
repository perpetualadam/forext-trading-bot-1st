# Filesystem guard review

The D.11 filesystem guard denies paths whose names or folders indicate `.env`, credentials, `data/ops`, `v2_shadow`, or `pgdata`. It wraps `builtins.open`, `Path.open`, `os.open`, `os.replace`, `os.rename`, `os.remove`, `os.unlink`, `shutil.move`, `shutil.copy`, `shutil.copy2`, and `shutil.rmtree`.

`shutil.copyfile` and `shutil.copytree` are not wrapped by that existing guard. The D.15 schedules do not call them. The gap is recorded and was not closed by weakening or widening the guard during this audit.

Safety writes used the temporary `LIVE_SAFETY_STATE_PATH` only. Production operational-state and shadow-state mounts were not read or written. Real `.env` files were not read.
