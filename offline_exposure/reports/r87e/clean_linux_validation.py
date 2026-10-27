"""R.87E source-only native Linux checkout; never install or contact a broker.

Uses a disposable repository with a read-only local object-store alternate.
Only the listed tracked source/archive paths are materialized. No source repo
index/ref/worktree is changed, and no credential/global Git config is loaded.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

os.environ.clear()
source = Path(sys.argv[1]).resolve()
reports = Path(__file__).resolve().parent
sha = "9ba819cf1f08b92780a19df5f1d8e54df2c2134d"
paths = [
    ".gitattributes", "offline_exposure/fake_coordinator.py",
    "offline_exposure/test_contract.py", "offline_exposure/run_checks.py",
    "forex_bot/exposure_view.py", "forex_bot/bot_loop.py",
    "data/research/adaptive_ensemble/r86/R86_SOURCE_REVIEW.zip",
    "tests/test_d15_historical_compatibility.py", "tests/g14_4_acquire.py",
    "tests/g14_7_fs.py", "forex_bot/app.py", "forex_bot/database.py",
    "forex_bot/telegram_control.py", "forex_bot/live_safety.py",
    "forex_bot/strategy_meta.py",
    "data/historical/EUR_USD_M5.csv",
]
work = Path(tempfile.mkdtemp(prefix="r87e-clean-"))
template = work / "empty-template"
template.mkdir()
repo = work / "checkout"
env = {"PATH": "/usr/bin:/bin", "HOME": str(work), "LANG": "C.UTF-8",
       "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_TERMINAL_PROMPT": "0"}


def git(*args):
    result = subprocess.run(["/usr/bin/git", *args], cwd=repo if repo.exists() else work,
                            env=env, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


git("init", "--quiet", "--initial-branch=main", "--template=" + str(template), str(repo))
(repo / ".git/objects/info/alternates").write_text(str(source / ".git/objects") + "\n")
git("config", "core.sparseCheckout", "true")
git("config", "core.sparseCheckoutCone", "false")
(repo / ".git/info").mkdir(exist_ok=True)
(repo / ".git/info/sparse-checkout").write_text("\n".join("/" + p for p in paths) + "\n")
git("read-tree", "-mu", sha)
git("update-ref", "refs/heads/main", sha)  # existing commit only, no new commit
assert git("rev-parse", "HEAD") == sha
assert git("status", "--porcelain") == ""
assert all((repo / p).is_file() for p in paths)
assert not (repo / ".env").exists()
before = {p: hashlib.sha256((repo / p).read_bytes()).hexdigest() for p in paths}
start = time.monotonic()
result = subprocess.run([sys.executable, "-I", "-S", "-B", "offline_exposure/run_checks.py"],
                        cwd=repo, env=env, capture_output=True, text=True, timeout=60)
duration = time.monotonic() - start
(reports / "linux_clean_runner.log").write_text(result.stdout + result.stderr, encoding="utf-8")
reproduction = subprocess.run([sys.executable, "-I", "-S", "-B",
                              str(reports / "representative_repro.py"), str(repo)],
                             cwd=repo, env=env, capture_output=True, text=True, timeout=30)
(reports / "representative_reproductions.json").write_text(reproduction.stdout, encoding="utf-8")
(reports / "representative_driver_stderr.log").write_text(reproduction.stderr, encoding="utf-8")
assert git("status", "--porcelain") == ""
assert before == {p: hashlib.sha256((repo / p).read_bytes()).hexdigest() for p in paths}
record = {"commit": sha, "platform": sys.platform, "python": sys.version,
          "git": git("--version"), "checkout": str(repo), "sparse": True,
          "tracked_paths": paths, "clean_before_after": True,
          "returncode": result.returncode, "wall_seconds": duration,
          "summary": re.findall(r"RESULT .*", result.stdout), "source_sha256": before,
          "representative_returncode": reproduction.returncode,
          "permissions": {p: oct((repo / p).stat().st_mode & 0o777) for p in paths},
          "untracked_fixture_dependencies": False}
dataset_blob = subprocess.run(["/usr/bin/git", "show", sha + ":data/historical/EUR_USD_M5.csv"],
                              cwd=repo, env=env, capture_output=True, timeout=30, check=True).stdout
record["dataset_blob_sha256"] = hashlib.sha256(dataset_blob).hexdigest()
(reports / "linux_clean_result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record, indent=2))
raise SystemExit(result.returncode or reproduction.returncode)
