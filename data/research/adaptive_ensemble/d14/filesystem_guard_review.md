# Filesystem guard review

Denied basenames are `.env` and names ending in `.env`, plus paths containing `data/ops`, `v2_shadow`, `credential`, or `pgdata`.

Wrapped operations are `builtins.open`, `Path.open`, `os.open`, `os.replace`, `os.rename`, `os.remove`, `os.unlink`, `shutil.move`, `shutil.copy`, `shutil.copy2`, and `shutil.rmtree`.

`shutil.copyfile` and `shutil.copytree` are not separately wrapped. The D.14 schedules did not need them. Guards were not weakened.
