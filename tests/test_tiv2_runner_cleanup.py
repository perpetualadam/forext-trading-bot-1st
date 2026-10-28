"""Real isolated entrypoints must clean only their own workspace on every exit."""

import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "data/research/trading_intelligence_v2"
RUNNERS = [
    ("managed_run.py", "--tests", "test_contract"),
    ("managed_run.py", "--mtf-tests", "test_mtf"),
    ("managed_run.py", "--v23-tests", "test_v23"),
    ("v24_run.py", "--v24-tests", "test_v24"),
    ("v25_run.py", "--v25-tests", "test_v25"),
    ("v26_run.py", "--tests", "test_v26"),
    ("v26b_run.py", "--tests", "test_v26b"),
]

STUB_TEST = '''
import os
from pathlib import Path
import sys
import unittest

class Contract(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(dict(os.environ), {})
        if os.name != "nt":
            self.assertEqual(TEMP.stat().st_mode & 0o077, 0)
        (TEMP / "nested").mkdir()
        (TEMP / "nested" / "fixture.txt").write_text("synthetic fixture")
        for event in ("socket.connect", "subprocess.Popen", "ctypes.dlopen"):
            with self.assertRaisesRegex(PermissionError, "TIV2_OFFLINE_BLOCKED"):
                sys.audit(event, None)
        for module in ("forex_bot", "dotenv", "psycopg2", "sqlite3", "requests", "http", "urllib", "socket", "subprocess", "ctypes"):
            with self.assertRaisesRegex(PermissionError, "TIV2_IMPORT_BLOCKED"):
                sys.audit("import", module, None, None, None, None)
        # Cached stdlib modules need not re-emit import events. Verify an actual
        # forbidden application import as well as every policy event above.
        with self.assertRaisesRegex(PermissionError, "TIV2_IMPORT_BLOCKED"):
            __import__("forex_bot")
        with self.assertRaisesRegex(PermissionError, "TIV2_FD_BLOCKED"):
            open(1, "w", closefd=False)
        with self.assertRaisesRegex(PermissionError, "TIV2_WRITE_BLOCKED"):
            (ROOT / "outside.txt").write_text("must not overwrite")
        with self.assertRaisesRegex(PermissionError, "TIV2_READ_BLOCKED"):
            (ROOT / "outside.txt").read_text()
        with self.assertRaisesRegex(PermissionError, "TIV2_MUTATION_BLOCKED"):
            (ROOT / "outside-dir").mkdir()
        for name in (".env", "state.sqlite", "state.permit", "state.consumed"):
            with self.assertRaisesRegex(PermissionError, "TIV2_STATE_BLOCKED"):
                (TEMP / name).write_text("must not persist")
        if MODE == "test_failure":
            self.fail("synthetic test failure")
'''


def run_fixture(tmp_path, runner, argument, test_module, mode):
    root = tmp_path / "repo"
    package = root / "data/research/trading_intelligence_v2"
    package.mkdir(parents=True)
    parent = tmp_path / "os-temp"
    parent.mkdir()
    sibling = parent / "tiv2-preserve-sibling"
    sibling.mkdir()
    (sibling / "data.txt").write_text("preserve local data")
    (root / "outside.txt").write_text("preserve local data")
    for name in {runner, "run.py", "_runner_temp.py"}:
        shutil.copyfile(SOURCE / name, package / name)
    # The audit barrier must already be installed at the first package import.
    bootstrap = '''import sys
TEMP = sys.modules["__main__"].TEMP
print("TIV2_TEMP_PATH=" + str(TEMP), flush=True)
try:
    sys.audit("socket.connect", None)
except PermissionError:
    pass
else:
    raise AssertionError("network barrier missing before package import")
'''
    if mode == "startup_failure":
        bootstrap += 'raise RuntimeError("synthetic startup failure")\n'
    (package / "__init__.py").write_text(bootstrap)
    body = "MODE = " + repr(mode) + "\n" + STUB_TEST
    if mode == "interrupt":
        body += '\nraise KeyboardInterrupt("synthetic interrupt")\n'
    if mode == "explicit_exit":
        body += '\nraise SystemExit(23)\n'
    (package / (test_module + ".py")).write_text(body)
    env = dict(os.environ, TMP=str(parent), TEMP=str(parent), TMPDIR=str(parent))
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", str(package / runner), argument],
        cwd=root, env=env, capture_output=True, text=True, timeout=30,
    )
    match = re.search(r"^TIV2_TEMP_PATH=(.+)$", result.stdout, re.MULTILINE)
    assert match, result.stdout + result.stderr
    workspace = Path(match[1].strip())
    assert workspace.parent == parent.resolve()
    assert not workspace.exists(), result.stdout + result.stderr
    assert (sibling / "data.txt").read_text() == "preserve local data"
    assert (root / "outside.txt").read_text() == "preserve local data"
    assert not (root / "outside-dir").exists()
    assert sorted(path.name for path in parent.iterdir()) == [sibling.name]
    assert not list(root.glob("tiv2-*"))
    return result


@pytest.mark.parametrize("runner,argument,test_module", RUNNERS)
@pytest.mark.parametrize("mode", ["success", "test_failure", "startup_failure", "interrupt", "explicit_exit"])
def test_entrypoint_cleanup_preserves_safety_and_exit_status(tmp_path, runner, argument, test_module, mode):
    result = run_fixture(tmp_path, runner, argument, test_module, mode)
    if mode == "success":
        assert result.returncode == 0, result.stdout + result.stderr
    elif mode == "explicit_exit":
        assert result.returncode == 23, result.stderr
    else:
        assert result.returncode != 0
        expected = {"test_failure": "synthetic test failure", "startup_failure": "synthetic startup failure", "interrupt": "KeyboardInterrupt"}[mode]
        assert expected in result.stderr


@pytest.fixture
def helper(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("tiv2_temp_cleanup_test", SOURCE / "_runner_temp.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.tempfile, "tempdir", str(tmp_path))
    return module


def test_replaced_root_is_preserved_and_cleanup_failure_is_visible(helper):
    with pytest.raises(PermissionError, match="TIV2_TEMP_IDENTITY_CHANGED"):
        with helper.temporary_workspace() as root:
            moved = root.with_name(root.name + "-original")
            root.rename(moved)
            root.mkdir()
            (root / "replacement.txt").write_text("preserve replacement")
    assert moved.is_dir()
    assert (root / "replacement.txt").read_text() == "preserve replacement"


def test_reparse_entry_is_preserved_without_following_it(helper, monkeypatch):
    original = helper._is_link
    with pytest.raises(PermissionError, match="TIV2_TEMP_LINK_REFUSED"):
        with helper.temporary_workspace() as root:
            entry = root / "reparse-fixture"
            entry.write_text("preserve link target")
            identity = entry.stat().st_ino
            monkeypatch.setattr(helper, "_is_link", lambda info: info.st_ino == identity or original(info))
    assert entry.read_text() == "preserve link target"


def test_cleanup_permission_failure_is_not_silenced(helper, monkeypatch):
    def refuse_unlink(*_args, **_kwargs):
        raise PermissionError("synthetic cleanup denial")

    with monkeypatch.context() as patcher:
        with pytest.raises(PermissionError, match="synthetic cleanup denial"):
            with helper.temporary_workspace() as root:
                entry = root / "fixture.txt"
                entry.write_text("synthetic fixture")
                patcher.setattr(Path, "unlink", refuse_unlink)
    assert entry.read_text() == "synthetic fixture"
    identity = root.stat()
    helper._cleanup_owned_tree(root, (identity.st_dev, identity.st_ino))
    assert not root.exists()


def test_managed_launcher_refuses_modified_frozen_source_before_allocating(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    parent = tmp_path / "os-temp"
    parent.mkdir()
    for name in ("managed_run.py", "run.py", "_runner_temp.py"):
        shutil.copyfile(SOURCE / name, package / name)
    with (package / "run.py").open("ab") as source:
        source.write(b"\nraise AssertionError('tampered source executed')\n")
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", str(package / "managed_run.py"), "--tests"],
        env=dict(os.environ, TMP=str(parent), TEMP=str(parent), TMPDIR=str(parent)),
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "TIV2_FROZEN_RUNNER_CHANGED" in result.stderr
    assert "tampered source executed" not in result.stderr
    assert list(parent.iterdir()) == []
