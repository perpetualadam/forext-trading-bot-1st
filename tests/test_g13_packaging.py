"""Synthetic and repository checks for the Stage G.13 Dockerfile repair."""

from __future__ import annotations

import importlib.util
import hashlib
import os
import stat
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("g13_packaging", Path(__file__).with_name("g13_packaging.py"))
if _spec is None or _spec.loader is None:
    raise RuntimeError("g13_packaging module spec is unavailable")
g13_packaging = importlib.util.module_from_spec(_spec)
sys.modules["g13_packaging"] = g13_packaging
_spec.loader.exec_module(g13_packaging)

ENTRYPOINT = g13_packaging.ENTRYPOINT
PIP_COMMAND = g13_packaging.PIP_COMMAND
ROOT = g13_packaging.ROOT
allowlist_paths = g13_packaging.allowlist_paths
application_copy_paths = g13_packaging.application_copy_paths
dockerignore_rules = g13_packaging.dockerignore_rules
is_reparse_point = g13_packaging.is_reparse_point
load_allowlist = g13_packaging.load_allowlist
parse_copies = g13_packaging.parse_copies
production_closure = g13_packaging.production_closure
render_dockerfile = g13_packaging.render_dockerfile
sha256_file = g13_packaging.sha256_file
verify_dockerfile = g13_packaging.verify_dockerfile

PATHS = [
    ".dockerignore",
    "Dockerfile",
    "requirements.txt",
    "main.py",
    "forex_bot/app.py",
]
ORIGINAL_DOCKERFILE_SHA256 = "f8d537d84c8ab004c5fc2cbdc5ef58e8141f5ca66a13be6cc5eac38c7c7006a6"


def _tree(root: Path) -> None:
    (root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (root / "main.py").write_text("print('ok')\n", encoding="utf-8")
    package = root / "forex_bot"
    package.mkdir()
    (package / "app.py").write_text("app = object()\n", encoding="utf-8")
    (root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (root / ".dockerignore").write_text(".git\n", encoding="utf-8")


def _verify(text: str, root: Path, rules: list[dict] | None = None) -> dict:
    return verify_dockerfile(text, paths=PATHS, root=root, rules=rules)


def test_repository_dockerfile_matches_audited_allowlist() -> None:
    document = load_allowlist()
    paths = allowlist_paths(document)
    assert document["file_count"] == len(paths)
    assert len(paths) == len(set(paths))
    assert all(not path.startswith(("forex_bot/research/", "tests/", "data/")) for path in paths)
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert sha256_file(ROOT / "Dockerfile") != ORIGINAL_DOCKERFILE_SHA256
    assert "COPY forex_bot ./forex_bot" not in dockerfile
    assert dockerfile.count("COPY main.py ") == 1
    result = verify_dockerfile(dockerfile, paths=paths, root=ROOT, rules=dockerignore_rules())
    assert result["ok"], result
    assert result["copy_count"] == len(paths) - 2
    assert result["main_py_copies"] == 1
    assert set(parse_copies(dockerfile.replace("\r\n", "\n"))) == {
        (rel, "./main.py" if rel == "main.py" else "." if rel == "requirements.txt" else f"./{rel}")
        for rel in application_copy_paths(paths)
    }


def test_rendered_dockerfile_preserves_install_and_entrypoint() -> None:
    text = render_dockerfile(allowlist_paths(load_allowlist())).replace("\r\n", "\n")
    assert PIP_COMMAND in text
    assert text.count(ENTRYPOINT) == 1
    assert "WORKDIR /app" in text


def test_production_closure_matches_allowlist_python_files() -> None:
    closure = production_closure()
    python_files = {path for path in allowlist_paths(load_allowlist()) if path.endswith(".py")}
    assert closure["missing"] == []
    assert closure["dynamic_calls"] == []
    assert set(closure["modules"]) == python_files


def test_current_packaging_source_seals() -> None:
    for row in load_allowlist()["files"]:
        data = (ROOT / row["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest() == row["sha256"], row["path"]


def test_computed_import_remains_a_packaging_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(g13_packaging, "ENTRY_MODULES", ("main.py",))
    (tmp_path / "main.py").write_text('__import__("uuid")\n__import__(runtime_name)\n')
    closure = production_closure(tmp_path)
    assert closure["dynamic_calls"] == ["main.py:2:__import__"]


def test_package_import_includes_the_requested_module() -> None:
    import ast
    imports = g13_packaging.resolve_import("main.py", ast.parse("from forex_bot import startup_recovery").body[0])
    assert "forex_bot/startup_recovery.py" in imports


def test_missing_allowlist_entry(tmp_path: Path) -> None:
    _tree(tmp_path)
    text = render_dockerfile(PATHS).replace("\r\n", "\n").replace(
        "COPY forex_bot/app.py ./forex_bot/app.py\n",
        "",
    )
    result = _verify(text, tmp_path)
    assert not result["ok"]
    assert "forex_bot/app.py" in result["missing"]


def test_unexpected_extra_file(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / "extra.py").write_text("x = 1\n", encoding="utf-8")
    text = render_dockerfile(PATHS) + "COPY extra.py ./extra.py\n"
    result = _verify(text, tmp_path)
    assert "extra.py" in result["extra"]


def test_duplicate_main_py(tmp_path: Path) -> None:
    _tree(tmp_path)
    text = render_dockerfile(PATHS) + "COPY main.py ./main.py\n"
    result = _verify(text, tmp_path)
    assert "main_py_not_copied_once" in result["findings"]
    assert any(item.startswith("duplicate_destination") for item in result["findings"])


def test_broad_copy(tmp_path: Path) -> None:
    _tree(tmp_path)
    result = _verify("WORKDIR /app\n" + PIP_COMMAND + "\n" + ENTRYPOINT + "\nCOPY forex_bot ./forex_bot\n", tmp_path)
    assert "broad_package_copy" in result["findings"]


def test_wildcard_copy(tmp_path: Path) -> None:
    _tree(tmp_path)
    text = render_dockerfile(PATHS) + "COPY forex_bot/*.py ./forex_bot/\n"
    result = _verify(text, tmp_path)
    assert "wildcard_copy" in result["findings"]


def test_path_traversal(tmp_path: Path) -> None:
    _tree(tmp_path)
    text = render_dockerfile(PATHS) + "COPY ../g13_secret.py ./g13_secret.py\n"
    result = _verify(text, tmp_path)
    assert "unsafe_source" in result["findings"]


def test_destination_escape(tmp_path: Path) -> None:
    _tree(tmp_path)
    text = render_dockerfile(PATHS).replace("COPY main.py ./main.py", "COPY main.py /tmp/main.py")
    result = _verify(text, tmp_path)
    assert any(item.startswith("destination_escapes_app") for item in result["findings"])


def test_symlink_source_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _tree(tmp_path)
    real_is_symlink = Path.is_symlink

    def fake_is_symlink(self: Path) -> bool:
        if self.name == "app.py":
            return True
        return real_is_symlink(self)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
    result = _verify(render_dockerfile(PATHS), tmp_path)
    assert any(item == "symlink_or_reparse:forex_bot/app.py" for item in result["findings"])


def test_reparse_point_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _tree(tmp_path)
    original = os.lstat

    class _Info:
        st_mode = stat.S_IFREG
        st_file_attributes = 0x400

    def flagged(path: os.PathLike[str] | str) -> _Info | os.stat_result:
        if str(path).endswith("app.py"):
            return _Info()
        return original(path)

    monkeypatch.setattr("g13_packaging.os.lstat", flagged)
    assert is_reparse_point(tmp_path / "forex_bot" / "app.py")
    result = _verify(render_dockerfile(PATHS), tmp_path)
    assert any(item == "symlink_or_reparse:forex_bot/app.py" for item in result["findings"])


def test_duplicate_destination(tmp_path: Path) -> None:
    _tree(tmp_path)
    text = render_dockerfile(PATHS).replace(
        "COPY forex_bot/app.py ./forex_bot/app.py",
        "COPY forex_bot/app.py ./main.py",
    )
    result = _verify(text, tmp_path)
    assert any(item.startswith("duplicate_destination") for item in result["findings"])


def test_dockerignore_excluded_source(tmp_path: Path) -> None:
    _tree(tmp_path)
    rules = [{"pattern": "main.py", "exclude": True, "negated": False}]

    def excluded(rel: str, active: list[dict] | None = None) -> bool:
        return rel == "main.py" and active == rules

    original = getattr(g13_packaging, "source_excluded")
    setattr(g13_packaging, "source_excluded", excluded)
    try:
        result = _verify(render_dockerfile(PATHS), tmp_path, rules)
    finally:
        setattr(g13_packaging, "source_excluded", original)
    assert any(item == "dockerignore_excluded:main.py" for item in result["findings"])


def test_incorrect_workdir_and_startup_command(tmp_path: Path) -> None:
    _tree(tmp_path)
    text = render_dockerfile(PATHS).replace("WORKDIR /app", "WORKDIR /tmp").replace(
        ENTRYPOINT,
        'CMD ["python", "main.py"]',
    )
    result = _verify(text, tmp_path)
    assert "workdir_changed" in result["findings"]
    assert "entrypoint_changed" in result["findings"]


def test_credential_file_and_bad_dependency_command(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    text = render_dockerfile(PATHS).replace("\r\n", "\n").replace(
        PIP_COMMAND,
        "RUN pip install -r requirements.txt",
    )
    text += "COPY .env ./.env\n"
    result = _verify(text, tmp_path)
    assert "dependency_install_changed" in result["findings"]
    assert any(item.startswith("credential_source") for item in result["findings"])
