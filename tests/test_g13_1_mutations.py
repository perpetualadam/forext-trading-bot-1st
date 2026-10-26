"""Synthetic regressions for the migrated G.13.1 packaging checks."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import stat
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("g13_1_baseline", Path(__file__).with_name("g13_1_baseline.py"))
if _spec is None or _spec.loader is None:
    raise RuntimeError("g13.1 baseline helper is unavailable")
baseline = importlib.util.module_from_spec(_spec)
sys.modules["g13_1_baseline"] = baseline
_spec.loader.exec_module(baseline)

PATHS = [
    ".dockerignore",
    "Dockerfile",
    "requirements.txt",
    "main.py",
    "forex_bot/app.py",
]
OLD_DOCKER = b"FROM old\n"
NEW_DOCKER = b"FROM authorised\n"
APP = b"app = object()\n"
OLD_SHA = hashlib.sha256(OLD_DOCKER).hexdigest()
NEW_SHA = hashlib.sha256(NEW_DOCKER).hexdigest()
APP_SHA = hashlib.sha256(APP).hexdigest()


def _tree(root: Path) -> None:
    (root / "requirements.txt").write_bytes(b"fastapi\n")
    (root / "main.py").write_bytes(b"print('ok')\n")
    package = root / "forex_bot"
    package.mkdir()
    (package / "app.py").write_bytes(APP)
    (root / "Dockerfile").write_bytes(NEW_DOCKER)
    (root / ".dockerignore").write_bytes(b".git\n")


def _rows() -> list[dict[str, str]]:
    return [
        {"path": "Dockerfile", "sha256": OLD_SHA},
        {"path": "forex_bot/app.py", "sha256": APP_SHA},
        {"path": "main.py", "sha256": hashlib.sha256(b"print('ok')\n").hexdigest()},
        {"path": "requirements.txt", "sha256": hashlib.sha256(b"fastapi\n").hexdigest()},
        {"path": ".dockerignore", "sha256": hashlib.sha256(b".git\n").hexdigest()},
    ]


def _manifest() -> dict[str, str]:
    return {row["path"]: row["sha256"] for row in _rows()}


def _evaluate(root: Path, rows: list[dict[str, str]] | None = None, expected: set[str] | None = None):
    chosen = rows if rows is not None else _rows()
    return baseline.evaluate_allowlist(
        chosen,
        root,
        expected_paths=expected if expected is not None else {row["path"] for row in chosen},
        manifest_hashes={row["path"]: row["sha256"] for row in chosen},
        authorised_dockerfile=NEW_SHA,
        historical_dockerfile=OLD_SHA,
    )


def _render() -> str:
    return baseline._packaging().render_dockerfile(PATHS).replace("\r\n", "\n")


def _packaging(text: str, root: Path, paths: list[str] | None = None) -> dict:
    return baseline.packaging_problems(text, paths if paths is not None else PATHS, root)


def test_changed_allowlisted_python_file_fails() -> None:
    recorded = [
        {"path": "Dockerfile", "sha256": OLD_SHA},
        {"path": "forex_bot/app.py", "sha256": APP_SHA},
    ]
    accepted = baseline.compare_snapshot_files(
        [
            {"path": "Dockerfile", "sha256": NEW_SHA},
            {"path": "forex_bot/app.py", "sha256": APP_SHA},
        ],
        recorded,
        authorised_dockerfile=NEW_SHA,
        historical_dockerfile=OLD_SHA,
    )
    assert accepted["ok"]
    rejected = baseline.compare_snapshot_files(
        [
            {"path": "Dockerfile", "sha256": NEW_SHA},
            {"path": "forex_bot/app.py", "sha256": "f" * 64},
        ],
        recorded,
        authorised_dockerfile=NEW_SHA,
        historical_dockerfile=OLD_SHA,
    )
    assert not rejected["ok"]
    assert "unexpected_source_drift" in rejected["problems"]


def test_changed_dockerfile_hash_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert _evaluate(tmp_path)["ok"]
    (tmp_path / "Dockerfile").write_bytes(b"FROM unexpected\n")
    rejected = _evaluate(tmp_path)
    assert not rejected["ok"]
    assert "dockerfile_hash" in rejected["problems"]


def test_removed_allowlisted_file_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert _evaluate(tmp_path)["ok"]
    (tmp_path / "forex_bot" / "app.py").unlink()
    rejected = _evaluate(tmp_path)
    assert not rejected["ok"]
    assert "missing:forex_bot/app.py" in rejected["problems"]


def test_unauthorised_allowlist_entry_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / "extra.py").write_text("x = 1\n", encoding="utf-8")
    extra = hashlib.sha256(b"x = 1\n").hexdigest()
    rows = [*_rows(), {"path": "extra.py", "sha256": extra}]
    rejected = _evaluate(tmp_path, rows, {row["path"] for row in _rows()})
    assert not rejected["ok"]
    assert "allowlist_paths" in rejected["problems"]


def test_rewritten_dockerfile_pin_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    rows = _rows()
    for row in rows:
        if row["path"] == "Dockerfile":
            row["sha256"] = NEW_SHA
    rejected = _evaluate(tmp_path, rows)
    assert not rejected["ok"]
    assert "allowlist_dockerfile_pin_changed" in rejected["problems"]


def test_clean_explicit_copy_is_accepted(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert _packaging(_render(), tmp_path)["ok"]


def test_broad_context_copy_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    rejected = _packaging(_render() + "COPY . .\n", tmp_path)
    assert not rejected["ok"]
    assert "unrestricted_context_copy" in rejected["findings"]


def test_broad_package_copy_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    rejected = _packaging(_render() + "COPY    forex_bot/     ./forex_bot/\n", tmp_path)
    assert not rejected["ok"]
    assert "broad_package_copy" in rejected["findings"]


def test_wildcard_copy_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    rejected = _packaging(_render() + "COPY forex_bot/*.py ./forex_bot/\n", tmp_path)
    assert not rejected["ok"]
    assert "wildcard_copy" in rejected["findings"]


def test_duplicate_main_copy_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    rejected = _packaging(_render() + "COPY main.py ./main.py\n", tmp_path)
    assert not rejected["ok"]
    assert "main_py_not_copied_once" in rejected["findings"]


def test_env_copy_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    paths = [*PATHS, ".env"]
    rejected = _packaging(_render() + "COPY .env ./.env\n", tmp_path, paths)
    assert not rejected["ok"]
    assert any(item.startswith(("forbidden_source", "credential_source")) for item in rejected["findings"])


def test_test_fixture_copy_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    fixture = tmp_path / "tests"
    fixture.mkdir()
    (fixture / "test_fixture.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    paths = [*PATHS, "tests/test_fixture.py"]
    rejected = _packaging(_render() + "COPY tests/test_fixture.py ./test_fixture.py\n", tmp_path, paths)
    assert not rejected["ok"]
    assert any(item.startswith("forbidden_source") for item in rejected["findings"])


def test_research_artifact_copy_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    research = tmp_path / "forex_bot" / "research"
    research.mkdir()
    (research / "note.py").write_text("x = 1\n", encoding="utf-8")
    paths = [*PATHS, "forex_bot/research/note.py"]
    rejected = _packaging(
        _render() + "COPY forex_bot/research/note.py ./forex_bot/research/note.py\n",
        tmp_path,
        paths,
    )
    assert not rejected["ok"]
    assert any(item.startswith("forbidden_source") for item in rejected["findings"])


def test_operational_state_copy_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    ops = tmp_path / "data" / "ops"
    ops.mkdir(parents=True)
    (ops / "live_safety_state.json").write_text("{}\n", encoding="utf-8")
    paths = [*PATHS, "data/ops/live_safety_state.json"]
    rejected = _packaging(
        _render() + "COPY data/ops/live_safety_state.json ./live_safety_state.json\n",
        tmp_path,
        paths,
    )
    assert not rejected["ok"]
    assert any(item.startswith("forbidden_source") for item in rejected["findings"])


def test_changed_startup_command_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    text = _render().replace(baseline._packaging().ENTRYPOINT, 'CMD ["python", "main.py"]')
    rejected = _packaging(text, tmp_path)
    assert not rejected["ok"]
    assert "entrypoint_changed" in rejected["findings"]


def test_changed_dependency_install_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    text = _render().replace(baseline._packaging().PIP_COMMAND, "RUN pip install -r requirements.txt")
    rejected = _packaging(text, tmp_path)
    assert not rejected["ok"]
    assert "dependency_install_changed" in rejected["findings"]


def test_path_traversal_fails(tmp_path: Path) -> None:
    _tree(tmp_path)
    rejected = _packaging(_render() + "COPY ../secret.py ./secret.py\n", tmp_path)
    assert not rejected["ok"]
    assert "unsafe_source" in rejected["findings"]


def test_symlink_source_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _tree(tmp_path)
    real = Path.is_symlink

    def fake(self: Path) -> bool:
        return self.name == "app.py" or real(self)

    monkeypatch.setattr(Path, "is_symlink", fake)
    rejected = _packaging(_render(), tmp_path)
    assert not rejected["ok"]
    assert any(item == "symlink_or_reparse:forex_bot/app.py" for item in rejected["findings"])


def test_reparse_point_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _tree(tmp_path)
    original = os.lstat

    class _Info:
        st_mode = stat.S_IFREG
        st_file_attributes = 0x400

    def flagged(path: os.PathLike[str] | str) -> _Info | os.stat_result:
        if str(path).endswith("app.py"):
            return _Info()
        return original(path)

    baseline._packaging()
    monkeypatch.setattr("g13_packaging.os.lstat", flagged)
    rejected = _packaging(_render(), tmp_path)
    assert not rejected["ok"]
    assert any(item == "symlink_or_reparse:forex_bot/app.py" for item in rejected["findings"])


def test_json_copy_syntax_fails_closed(tmp_path: Path) -> None:
    _tree(tmp_path)
    rejected = _packaging(_render() + 'COPY ["forex_bot/", "./forex_bot/"]\n', tmp_path)
    assert not rejected["ok"]
    assert "unsupported_copy_syntax" in rejected["findings"]
