"""Offline Windows filesystem trust-boundary tests. No network and no production paths."""

from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest


def _load():
    path = Path(__file__).with_name("g14_7_fs.py")
    spec = importlib.util.spec_from_file_location("g14_7_fs_g148", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("filesystem_helper_missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FS = _load()


@pytest.fixture(autouse=True)
def deny_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("NETWORK_BOUNDARY_VIOLATION")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def _reject(parent: FS.DirectoryHandle, name: str, reason: str) -> None:
    before = set(parent.names)
    with pytest.raises(FS.FilesystemRejected) as caught:
        parent.write_exclusive(name, b"nope")
    assert caught.value.reason == reason
    assert set(parent.names) == before


def test_pre_open_replacement_binds_to_the_substitute(tmp_path: Path) -> None:
    """The first CreateFileW follows the object present at open time."""
    intended = tmp_path / "parent"
    decoy = tmp_path / "decoy"
    intended.mkdir()
    decoy.mkdir()
    (decoy / "marker.txt").write_bytes(b"m")
    original = FS.open_directory(intended)
    original_id = original.identity
    original.close()
    intended.rename(tmp_path / "intended-real")
    decoy.rename(intended)
    opened = FS.open_directory(intended)
    try:
        assert opened.identity != original_id
        child = opened.create_directory("child")
        handle = child.write_exclusive("note.bin", b"x")
        FS._kernel().CloseHandle(handle)
        child.close()
        assert list((tmp_path / "intended-real").iterdir()) == []
        assert (intended / "marker.txt").is_file()
        assert (intended / "child" / "note.bin").read_bytes() == b"x"
    finally:
        opened.close()


def test_swap_after_lstat_and_before_open(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    os.lstat(parent)
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "marker.txt").write_bytes(b"m")
    parent.rename(tmp_path / "real")
    decoy.rename(parent)
    opened = FS.open_directory(parent)
    try:
        assert (parent / "marker.txt").is_file()
        assert list((tmp_path / "real").iterdir()) == []
    finally:
        opened.close()


def test_rename_after_open_does_not_redirect_writes(tmp_path: Path) -> None:
    opened = FS.open_directory(tmp_path)
    try:
        child = opened.create_directory("child")
        (tmp_path / "child").rename(tmp_path / "child-real")
        (tmp_path / "child").mkdir()
        handle = child.write_exclusive("kept.bin", b"kept")
        FS._kernel().CloseHandle(handle)
        assert (tmp_path / "child-real" / "kept.bin").read_bytes() == b"kept"
        assert list((tmp_path / "child").iterdir()) == []
        child.close()
    finally:
        opened.close()


def test_junction_after_open_does_not_receive_the_write(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"
    target.mkdir()
    opened = FS.open_directory(tmp_path)
    try:
        child = opened.create_directory("child")
        (tmp_path / "child").rename(tmp_path / "child-real")
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(tmp_path / "child"), str(target)],
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            pytest.skip("NOT_EXECUTED_WITH_REASON: junction_creation_unavailable")
        handle = child.write_exclusive("kept.bin", b"kept")
        FS._kernel().CloseHandle(handle)
        assert (tmp_path / "child-real" / "kept.bin").read_bytes() == b"kept"
        assert list(target.iterdir()) == []
        child.close()
    finally:
        opened.close()


def test_junction_before_open_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip("NOT_EXECUTED_WITH_REASON: junction_creation_unavailable")
    with pytest.raises(FS.FilesystemRejected) as caught:
        FS.open_directory(link)
    assert caught.value.reason == "symlink_or_reparse"
    assert list(real.iterdir()) == []


def test_real_directory_symlink_when_available(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        os.symlink(real, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"NOT_EXECUTED_WITH_REASON: symlink_unavailable:{exc.errno}")
    with pytest.raises(FS.FilesystemRejected) as caught:
        FS.open_directory(link)
    assert caught.value.reason == "symlink_or_reparse"


def test_write_after_directory_removal_fails_closed(tmp_path: Path) -> None:
    opened = FS.open_directory(tmp_path)
    try:
        child = opened.create_directory("held")
        os.rmdir(tmp_path / "held")
        with pytest.raises(FS.FilesystemRejected) as caught:
            child.write_exclusive("x.bin", b"z")
        assert caught.value.reason == "handle_create_failed"
        assert not (tmp_path / "x.bin").exists()
        child.close()
    finally:
        opened.close()


def test_use_after_close_and_double_close(tmp_path: Path) -> None:
    opened = FS.open_directory(tmp_path)
    child = opened.create_directory("child")
    child.close()
    child.close()
    with pytest.raises(FS.FilesystemRejected) as caught:
        child.create_directory("nope")
    assert caught.value.reason == "handle_closed"
    with pytest.raises(FS.FilesystemRejected) as again:
        child.write_exclusive("nope.bin", b"z")
    assert again.value.reason == "handle_closed"
    opened.close()
    assert not (tmp_path / "child" / "nope").exists()
    assert not (tmp_path / "child" / "nope.bin").exists()


def test_duplicate_and_case_collision(tmp_path: Path) -> None:
    opened = FS.open_directory(tmp_path)
    try:
        opened.create_directory("Child")
        with pytest.raises(FS.FilesystemRejected) as caught:
            opened.create_directory("child")
        assert caught.value.reason == "case_collision"
        with pytest.raises(FS.FilesystemRejected) as duplicate:
            opened.create_directory("Child")
        assert duplicate.value.reason == "destination_exists"
    finally:
        opened.close()


def test_hard_link_name_is_not_replaced(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed.write_bytes(b"seed")
    os.link(seed, tmp_path / "link.bin")
    opened = FS.open_directory(tmp_path)
    try:
        with pytest.raises(FS.FilesystemRejected) as caught:
            opened.write_exclusive("link.bin", b"other")
        assert caught.value.reason == "unsafe_file_replacement"
        assert seed.read_bytes() == b"seed"
    finally:
        opened.close()


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("../escape.bin", "path_traversal"),
        ("C:/outside.bin", "path_traversal"),
        ("file:stream", "path_traversal"),
        ("\\\\server\\share\\x.bin", "path_traversal"),
        ("\\\\?\\C:\\outside.bin", "path_traversal"),
        ("\\\\.\\NUL", "path_traversal"),
        ("demo.whl.", "trailing_dot_or_space"),
        ("demo.whl ", "trailing_dot_or_space"),
        ("NUL", "reserved_device_name"),
        ("nul.txt", "reserved_device_name"),
        ("CON", "reserved_device_name"),
        ("COM1", "reserved_device_name"),
        ("a\nb", "control_character"),
    ],
)
def test_ambiguous_names_are_rejected(tmp_path: Path, name: str, reason: str) -> None:
    opened = FS.open_directory(tmp_path)
    try:
        _reject(opened, name, reason)
        assert name not in {path.name for path in tmp_path.iterdir()}
    finally:
        opened.close()


def test_child_stays_on_the_parent_volume(tmp_path: Path) -> None:
    opened = FS.open_directory(tmp_path)
    try:
        child = opened.create_directory("child")
        assert child.identity[0] == opened.identity[0]
        assert child.identity != opened.identity
        child.close()
    finally:
        opened.close()


def test_volume_mismatch_predicate_fails_closed() -> None:
    with pytest.raises(FS.FilesystemRejected) as caught:
        FS._require_same_volume((1, 0, 0), (2, 3, 4))
    assert caught.value.reason == "unexpected_volume"
    FS._require_same_volume((7, 1, 2), (7, 8, 9))
