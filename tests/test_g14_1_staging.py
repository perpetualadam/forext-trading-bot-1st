"""Offline tests for the minimal staging context. Synthetic fixtures only."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STAGE = _load("g14_1_stage")
VERIFY = _load("g14_1_verify")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _repo(tmp: Path) -> tuple[Path, list[str], dict[str, str], str, str]:
    files = {
        "Dockerfile": b"FROM scratch\nCOPY requirements.txt .\nCOPY main.py ./main.py\nCOPY forex_bot/app.py ./forex_bot/app.py\n",
        ".dockerignore": b".git\n",
        "requirements.txt": b"fastapi>=0.109.0\n",
        "main.py": b"print('ok')\n",
        "forex_bot/app.py": b"app = 1\n",
    }
    for rel, data in files.items():
        _write(tmp / rel, data)
    hashes = {rel: _sha(data) for rel, data in files.items()}
    return tmp, list(files), hashes, hashes["Dockerfile"], hashes[".dockerignore"]


def _stage(tmp: Path, repo: Path, paths: list[str], hashes: dict[str, str], docker: str, ignore: str):
    out = tmp / "stage"
    out.mkdir(parents=True)
    return STAGE.stage_context(
        repo,
        paths,
        hashes,
        authorised_dockerfile_sha256=docker,
        dockerignore_sha256=ignore,
        output_dir=out,
    ), out


def test_exact_permitted_paths_and_hashes(tmp_path: Path) -> None:
    repo, paths, hashes, docker, ignore = _repo(tmp_path / "repo")
    result, out = _stage(tmp_path, repo, paths, hashes, docker, ignore)
    assert [row["path"] for row in result["files"]] == sorted(paths)
    assert {row["path"]: row["sha256"] for row in result["files"]} == hashes
    assert result["approved"] is False
    checked = VERIFY.verify_directory(out, result["files"])
    assert checked["independent_verification"] == "PASS"
    assert checked["file_count"] == 5


def test_notes_and_backup_names_cannot_enter(tmp_path: Path) -> None:
    repo, paths, hashes, docker, ignore = _repo(tmp_path / "repo")
    _write(repo / "notes.txt", b"harmless\n")
    _write(repo / "main example .env backup.txt", b"dummy-backup\n")
    _write(repo / "# Copy to .env and fill in. docker.txt", b"dummy-docker\n")
    _write(repo / ".env", b"TOKEN=dummy\n")
    _write(repo / "credentials.json", b"{}\n")
    _write(repo / "data" / "ops" / "live_safety_state.json", b"{}\n")
    _write(repo / "forex_bot" / "research" / "study.py", b"x=1\n")
    _write(repo / "tests" / "fixture.py", b"x=1\n")
    _write(repo / ".git" / "config", b"[core]\n")
    result, out = _stage(tmp_path, repo, paths, hashes, docker, ignore)
    staged = {row["path"] for row in result["files"]}
    assert "notes.txt" not in staged
    assert "main example .env backup.txt" not in result["opened_paths"]
    assert "# Copy to .env and fill in. docker.txt" not in result["opened_paths"]
    assert not (out / "notes.txt").exists()
    assert not (out / ".env").exists()
    VERIFY.verify_directory(out, result["files"])


@pytest.mark.parametrize(
    ("relative", "reason"),
    [
        (".env", "credential"),
        (".env.local", "credential"),
        (".env.production", "credential"),
        ("credentials.json", "credential"),
        ("secrets/id_rsa", "credential"),
        ("forex_bot/research/study.py", "forbidden_tree"),
        ("tests/fixture.py", "forbidden_tree"),
        ("data/ops/live_safety_state.json", "credential"),
        ("notes.txt", "not_authorised_category"),
        ("main example .env backup.txt", "sensitive_backup"),
        ("# Copy to .env and fill in. docker.txt", "sensitive_backup"),
        ("broker/export.csv", "forbidden_suffix"),
        ("db/live.sqlite", "forbidden_suffix"),
    ],
)
def test_forbidden_names_are_rejected_even_if_listed(relative: str, reason: str) -> None:
    assert STAGE.forbidden_reason(relative) == reason


def test_missing_allowlisted_file_is_rejected(tmp_path: Path) -> None:
    repo, paths, hashes, docker, ignore = _repo(tmp_path / "repo")
    (repo / "forex_bot" / "app.py").unlink()
    with pytest.raises(STAGE.StagingRejected, match="missing:"):
        _stage(tmp_path, repo, paths, hashes, docker, ignore)


def test_path_traversal_wildcard_and_broad_copy_are_rejected(tmp_path: Path) -> None:
    repo, _paths, hashes, _docker, ignore = _repo(tmp_path / "repo")
    original = (repo / "Dockerfile").read_bytes()
    for index, (text, reason) in enumerate((
        (b"FROM scratch\nCOPY ../secret.txt ./secret.txt\n", "path_traversal"),
        (b"FROM scratch\nCOPY forex_bot/*.py ./forex_bot/\n", "unsupported_copy_syntax"),
        (b"FROM scratch\nCOPY forex_bot ./forex_bot\n", "broad_copy"),
        (b'FROM scratch\nCOPY ["main.py", "./main.py"]\n', "unsupported_copy_syntax"),
    )):
        _write(repo / "Dockerfile", text)
        digest = _sha(text)
        with pytest.raises(STAGE.StagingRejected, match=reason):
            _stage(tmp_path / f"{index}-{reason}", repo, ["Dockerfile"], {**hashes, "Dockerfile": digest}, digest, ignore)
    _write(repo / "Dockerfile", original)


def test_duplicate_destination_is_rejected(tmp_path: Path) -> None:
    repo, paths, hashes, _docker, ignore = _repo(tmp_path / "repo")
    text = b"FROM scratch\nCOPY main.py ./main.py\nCOPY requirements.txt ./main.py\nCOPY forex_bot/app.py ./forex_bot/app.py\n"
    _write(repo / "Dockerfile", text)
    digest = _sha(text)
    with pytest.raises(STAGE.StagingRejected, match="duplicate_destination"):
        _stage(tmp_path, repo, paths, {**hashes, "Dockerfile": digest}, digest, ignore)


def test_case_collision_is_rejected(tmp_path: Path) -> None:
    repo, paths, hashes, _docker, ignore = _repo(tmp_path / "repo")
    text = (
        b"FROM scratch\nCOPY requirements.txt .\nCOPY main.py ./main.py\n"
        b"COPY forex_bot/app.py ./forex_bot/app.py\nCOPY forex_bot/App.py ./forex_bot/App.py\n"
    )
    _write(repo / "Dockerfile", text)
    digest = _sha(text)
    paths = [*paths, "forex_bot/App.py"]
    hashes = {**hashes, "Dockerfile": digest, "forex_bot/App.py": hashes["forex_bot/app.py"]}
    with pytest.raises(STAGE.StagingRejected, match="case_collision"):
        _stage(tmp_path, repo, paths, hashes, digest, ignore)


def test_source_mutation_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, paths, hashes, docker, ignore = _repo(tmp_path / "repo")
    original = Path.read_bytes
    calls = {"app.py": 0}

    def flipping(self: Path) -> bytes:
        if self.name == "app.py" and "stage" not in self.parts:
            calls["app.py"] += 1
            if calls["app.py"] >= 2:
                return b"changed\n"
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", flipping)
    with pytest.raises(STAGE.StagingRejected, match="source_changed"):
        _stage(tmp_path, repo, paths, hashes, docker, ignore)


def test_staged_mutation_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, paths, hashes, docker, ignore = _repo(tmp_path / "repo")
    original = Path.read_bytes

    def flipping(self: Path) -> bytes:
        if "stage" in self.parts and self.name == "app.py":
            return b"tampered\n"
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", flipping)
    with pytest.raises(STAGE.StagingRejected, match="staged_hash_mismatch|source_changed"):
        _stage(tmp_path, repo, paths, hashes, docker, ignore)


def test_symlink_and_reparse_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, paths, hashes, docker, ignore = _repo(tmp_path / "repo")
    real = os.lstat

    def linked(path: os.PathLike[str] | str) -> os.stat_result:
        if Path(path).name == "app.py" and "stage" not in Path(path).parts:
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0, st_dev=1, st_ino=1, st_size=1)  # type: ignore[return-value]
        return real(path)

    monkeypatch.setattr(STAGE.os, "lstat", linked)
    with pytest.raises(STAGE.StagingRejected, match="symlink"):
        _stage(tmp_path, repo, paths, hashes, docker, ignore)

    def reparse(path: os.PathLike[str] | str) -> os.stat_result:
        if Path(path).name == "app.py" and "stage" not in Path(path).parts:
            return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400, st_dev=1, st_ino=1, st_size=1)  # type: ignore[return-value]
        return real(path)

    monkeypatch.setattr(STAGE.os, "lstat", reparse)
    with pytest.raises(STAGE.StagingRejected, match="reparse_or_placeholder"):
        _stage(tmp_path / "second", repo, paths, hashes, docker, ignore)


def test_verifier_rejects_an_unexpected_staged_file(tmp_path: Path) -> None:
    repo, paths, hashes, docker, ignore = _repo(tmp_path / "repo")
    result, out = _stage(tmp_path, repo, paths, hashes, docker, ignore)
    _write(out / "notes.txt", b"unexpected\n")
    with pytest.raises(VERIFY.VerificationRejected, match="path_set_mismatch|forbidden|unexpected"):
        VERIFY.verify_directory(out, result["files"])


def test_real_allowlist_accounting_is_sixty_three() -> None:
    payload = json.loads((ROOT / "data/research/adaptive_ensemble/g10/production_allowlist.json").read_text(encoding="utf-8"))
    paths = [row["path"] for row in payload["files"]]
    counts: dict[str, int] = {}
    for path in paths:
        kind = STAGE.classify_path(path)
        counts[kind] = counts.get(kind, 0) + 1
        assert VERIFY._normal(path) == path
        assert STAGE.forbidden_reason(path) is None
    assert sum(counts.values()) == 63
    assert counts == {
        "PYTHON_PACKAGE_FILE": 59,
        "APPLICATION_ENTRYPOINT": 1,
        "DEPENDENCY_MANIFEST": 1,
        "DOCKERFILE": 1,
        "DOCKERIGNORE": 1,
    }


def test_dockerfile_copy_set_matches_the_allowlist() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    copies = STAGE.parse_copies(text)
    sources = [source for source, _dest in copies]
    assert sources.count("main.py") == 1
    assert sources.count("requirements.txt") == 1
    assert "pip install --upgrade pip" in text
    assert "pip install --no-cache-dir --prefer-binary --timeout 120 --retries 15 -r requirements.txt" in text
    assert 'CMD ["uvicorn", "forex_bot.app:app", "--host", "0.0.0.0", "--port", "8000"]' in text
    payload = json.loads((ROOT / "tests/fixtures/current_production_allowlist.json").read_text(encoding="utf-8"))
    allow = {row["path"] for row in payload["files"]}
    assert set(sources) | {"Dockerfile", ".dockerignore"} == allow
    for source, _dest in copies:
        assert (ROOT / source).is_file()


def test_hash_mismatch_and_dockerignore_exclusion_are_rejected(tmp_path: Path) -> None:
    repo, paths, hashes, docker, ignore = _repo(tmp_path / "repo")
    bad = dict(hashes)
    bad["main.py"] = "0" * 64
    with pytest.raises(STAGE.StagingRejected, match="hash_mismatch:main.py"):
        _stage(tmp_path / "bad-hash", repo, paths, bad, docker, ignore)
    from forex_bot.research.adaptive_ensemble.g8_dockerignore import parse_dockerignore

    out = tmp_path / "ignored" / "stage"
    out.mkdir(parents=True)
    with pytest.raises(STAGE.StagingRejected, match="dockerignore_excludes_required:main.py"):
        STAGE.stage_context(
            repo,
            paths,
            hashes,
            authorised_dockerfile_sha256=docker,
            dockerignore_sha256=ignore,
            output_dir=out,
            dockerignore_rules=parse_dockerignore("main.py\n"),
        )


def test_frozen_hashes_match_authorised_values(historical_packaging_root) -> None:
    expected = {
        "Dockerfile": "4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad",
        ".dockerignore": "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd",
        "data/research/adaptive_ensemble/g10/production_allowlist.json": "b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4",
        "data/research/adaptive_ensemble/g10/source_snapshot.tar": "d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277",
        "data/research/adaptive_ensemble/g7/source_snapshot.tar": "0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82",
    }
    for rel, digest in expected.items():
        assert _sha(((ROOT if rel.startswith("data/") else historical_packaging_root) / rel).read_bytes()) == digest
