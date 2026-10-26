"""Offline remediation tests for G.14.5 findings. No network and no installs."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import stat
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGING = Path(r"C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2")
BASICS = {"SYSTEMROOT": r"C:\Windows", "WINDIR": r"C:\Windows"}
INTERPRETER = Path(r"C:\synthetic\python.exe")
WHEEL = "demo-1.0.0-py3-none-any.whl"
ARTIFACT = "https://files.pythonhosted.org/packages/aa/demo-1.0.0-py3-none-any.whl"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACQUIRE = _load("g14_4_acquire")
VERIFY = _load("g14_4_verify")
INVENTORY = _load("g14_4_inventory")


def _expect(error: type[BaseException], reason: str, call) -> None:
    with pytest.raises(error) as caught:
        call()
    assert getattr(caught.value, "reason", "") == reason


def _package(content: bytes, filename: str = WHEEL, **overrides: object) -> dict[str, object]:
    parsed = VERIFY.parse_wheel_filename(filename)
    assert parsed is not None
    package: dict[str, object] = {
        "name": parsed["name"],
        "version": parsed["version"],
        "filename": filename,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
        "direct": True,
        "extras": [],
        "markers": None,
        "requires": [],
        "provenance": "synthetic-fixture",
        "url": None,
        "vcs": None,
    }
    package.update(overrides)
    return package


def _manifest(packages: list[dict[str, object]], **overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": VERIFY.SCHEMA_VERSION,
        "synthetic": True,
        "status": VERIFY.SYNTHETIC_STATUS,
        "target": {
            "implementation": "cp",
            "python_major_minor": "3.12",
            "python_patch": "UNKNOWN",
            "os": "linux",
            "arch": "x86_64",
        },
        "source": {
            "index_url": VERIFY.SYNTHETIC_INDEX,
            "source_approved": False,
            "additional_indexes": [],
        },
        "packages": packages,
        "toolchain": {"pip_version": "UNKNOWN", "resolver": "UNKNOWN"},
        "claimed_state": None,
    }
    document.update(overrides)
    return document


def _house(tmp: Path, blobs: list[tuple[str, bytes]]) -> Path:
    wheelhouse = tmp / "wheelhouse"
    wheelhouse.mkdir(parents=True)
    for name, blob in blobs:
        (wheelhouse / name).write_bytes(blob)
    return wheelhouse


def _candidate(version: str = "1.0.0", **overrides: object) -> dict[str, object]:
    filename = f"demo-{version}-py3-none-any.whl"
    candidate: dict[str, object] = {
        "name": "demo",
        "version": version,
        "filename": filename,
        "url": f"https://files.pythonhosted.org/packages/aa/{filename}",
        "yanked": False,
        "partial": False,
    }
    candidate.update(overrides)
    return candidate


def _prepare(tmp: Path, requirements: str, candidates: list[dict[str, object]], **overrides: object):
    destination = tmp / "dest"
    destination.mkdir()
    arguments: dict[str, object] = {
        "inherited": {},
        "interpreter": INTERPRETER,
        "platform_basics": BASICS,
        "destination": destination,
        "requirements_text": requirements,
        "candidates": candidates,
    }
    arguments.update(overrides)
    return ACQUIRE.prepare_acquisition(**arguments)


@pytest.mark.parametrize(
    ("key", "reason"),
    [
        ("PIP_INDEX_URL", "inherited_environment_rejected"),
        ("PIP_EXTRA_INDEX_URL", "inherited_environment_rejected"),
        ("PIP_FIND_LINKS", "inherited_environment_rejected"),
        ("PIP_TRUSTED_HOST", "inherited_environment_rejected"),
        ("PIP_CONFIG_FILE", "inherited_environment_rejected"),
        ("PIP_PRE", "inherited_environment_rejected"),
        ("PIP_NO_BINARY", "inherited_environment_rejected"),
        ("PIP_CERT", "inherited_environment_rejected"),
        ("HTTPS_PROXY", "inherited_environment_rejected"),
        ("PYTHONSTARTUP", "inherited_environment_rejected"),
        ("UNEXPECTED_KEY", "unexpected_environment"),
    ],
)
def test_inherited_environment_is_rejected(key: str, reason: str) -> None:
    _expect(
        ACQUIRE.EnvironmentRejected,
        reason,
        lambda: ACQUIRE.build_acquisition_environment(
            {key: "synthetic-unapproved"},
            interpreter=INTERPRETER,
            platform_basics=BASICS,
        ),
    )


def test_credential_like_environment_value_is_rejected() -> None:
    _expect(
        ACQUIRE.EnvironmentRejected,
        "credential_value_rejected",
        lambda: ACQUIRE.build_acquisition_environment(
            {"AWS_SECRET_ACCESS_KEY": "synthetic"},
            interpreter=INTERPRETER,
            platform_basics=BASICS,
        ),
    )


def test_untrusted_executable_is_rejected() -> None:
    _expect(
        ACQUIRE.EnvironmentRejected,
        "untrusted_executable",
        lambda: ACQUIRE.select_interpreter(Path("python")),
    )


@pytest.mark.parametrize(
    ("url", "role", "reason"),
    [
        ("http://pypi.org/simple", "index", "http_url"),
        ("ftp://pypi.org/simple", "index", "ftp_url"),
        ("file:///tmp/demo.whl", "artifact", "file_url"),
        ("https://user:pass@pypi.org/simple", "index", "url_userinfo"),
        ("https://evil.example/simple", "index", "unapproved_host"),
        ("https://localhost/simple", "index", "localhost"),
        ("https://127.0.0.1/simple", "index", "loopback"),
        ("https://10.1.2.3/simple", "index", "private_address"),
        ("https://169.254.1.1/simple", "index", "link_local"),
        ("https://pypi.org:8443/simple", "index", "unexpected_port"),
        ("https://evil.example/demo-1.0.0-py3-none-any.whl", "artifact", "unexpected_artifact_host"),
    ],
)
def test_unapproved_urls_are_rejected(url: str, role: str, reason: str) -> None:
    _expect(ACQUIRE.PolicyRejected, reason, lambda: ACQUIRE.authorize_url(url, role=role))


def test_https_downgrade_redirect_is_rejected() -> None:
    _expect(
        ACQUIRE.PolicyRejected,
        "https_downgrade",
        lambda: ACQUIRE.authorize_redirect_chain(
            ["https://pypi.org/simple", "http://pypi.org/simple"],
            role="index",
        ),
    )


def test_cross_host_redirect_is_rejected() -> None:
    _expect(
        ACQUIRE.PolicyRejected,
        "cross_host_redirect",
        lambda: ACQUIRE.authorize_redirect_chain(
            ["https://pypi.org/simple", "https://evil.example/demo.whl"],
            role="index",
        ),
    )


def test_excessive_redirect_chain_is_rejected() -> None:
    urls = ["https://pypi.org/simple"] * 4
    _expect(
        ACQUIRE.PolicyRejected,
        "excessive_redirects",
        lambda: ACQUIRE.authorize_redirect_chain(urls, role="index"),
    )


def test_additional_index_is_rejected(tmp_path: Path) -> None:
    _expect(
        ACQUIRE.PolicyRejected,
        "unapproved_additional_index",
        lambda: _prepare(tmp_path, "demo>=1", [], extra_indexes=["https://mirror.example/simple"]),
    )


def test_direct_and_vcs_urls_are_rejected_by_acquisition_parser() -> None:
    _expect(
        INVENTORY.InventoryMismatch,
        "direct_url",
        lambda: INVENTORY.parse_requirement_line("requests @ https://files.example/requests.whl"),
    )
    _expect(
        INVENTORY.InventoryMismatch,
        "vcs_requirement",
        lambda: INVENTORY.parse_requirement_line("pandas @ git+https://example.invalid/pandas.git"),
    )


@pytest.mark.parametrize(
    ("filename", "reason"),
    [
        ("demo-1.0.0.tar.gz", "source_distribution"),
        ("demo-1.0.0.zip", "source_distribution"),
        ("demo-1.0.0-cp312-cp312-win_amd64.whl", "incorrect_architecture"),
    ],
)
def test_non_wheel_artifacts_are_rejected(filename: str, reason: str) -> None:
    _expect(
        ACQUIRE.AcquisitionRejected,
        reason,
        lambda: ACQUIRE.assess_wheel_candidate({"filename": filename, "version": "1.0.0", "url": ARTIFACT}),
    )


def test_conflicting_candidate_versions_are_rejected(tmp_path: Path) -> None:
    _expect(
        ACQUIRE.AcquisitionRejected,
        "conflicting_versions",
        lambda: _prepare(tmp_path, "demo>=1", [_candidate("1.0.0"), _candidate("2.0.0")]),
    )


def test_missing_wheel_candidate_is_rejected(tmp_path: Path) -> None:
    _expect(
        ACQUIRE.AcquisitionRejected,
        "missing_wheel",
        lambda: _prepare(tmp_path, "demo>=1\nother>=1\n", [_candidate()]),
    )


def test_unexpected_package_name_is_rejected(tmp_path: Path) -> None:
    _expect(
        ACQUIRE.AcquisitionRejected,
        "unexpected_package",
        lambda: _prepare(tmp_path, "demo>=1", [_candidate(name="other")]),
    )


def test_yanked_and_prerelease_candidates_are_rejected() -> None:
    _expect(
        ACQUIRE.AcquisitionRejected,
        "yanked_release",
        lambda: ACQUIRE.assess_wheel_candidate(_candidate(yanked=True)),
    )
    _expect(
        ACQUIRE.AcquisitionRejected,
        "unapproved_prerelease",
        lambda: ACQUIRE.assess_wheel_candidate(_candidate("1.0.0a1")),
    )


def test_requirement_forms_are_rejected() -> None:
    cases = [
        ("requests @ https://files.example/a.whl", "direct_url"),
        ("demo @ git+https://example.invalid/demo.git", "vcs_requirement"),
        ("-e .", "editable_requirement"),
        ("./localpkg", "local_path"),
        ("-r other.txt", "requirement_include"),
        ("-c constraints.txt", "constraint_include"),
        ("--index-url https://evil.example/simple", "index_override"),
        ("--find-links C:/wheels", "find_links_override"),
        ("demo>=1 ; sys_platform ==", "malformed_marker"),
    ]
    for text, reason in cases:
        _expect(INVENTORY.InventoryMismatch, reason, lambda text=text: INVENTORY.parse_requirement_line(text))
    _expect(
        INVENTORY.InventoryMismatch,
        "duplicate_requirement",
        lambda: INVENTORY.parse_requirement_document("demo>=1\ndemo>=1\n"),
    )


def _reject_bytes(tmp: Path, content: bytes, reason: str, **kwargs: object) -> None:
    filename = str(kwargs.pop("filename", WHEEL))
    limits = kwargs.pop("limits", None)
    package = _package(content, filename, **kwargs)
    arguments: dict[str, object] = {}
    if limits is not None:
        arguments["limits"] = limits

    def _call() -> None:
        VERIFY.verify_wheelhouse(_manifest([package]), _house(tmp, [(filename, content)]), **arguments)

    _expect(VERIFY.VerificationRejected, reason, _call)


def test_non_zip_payload_with_matching_hash_is_rejected(tmp_path: Path) -> None:
    _reject_bytes(tmp_path, b"this-is-not-a-zip", "malformed_zip")


def test_malformed_and_unsafe_archives_are_rejected(tmp_path: Path) -> None:
    _reject_bytes(tmp_path / "truncated", b"PK\x03\x04truncated", "malformed_zip")
    encrypted = io.BytesIO()
    with zipfile.ZipFile(encrypted, "w") as archive:
        archive.writestr("demo-1.0.0.dist-info/WHEEL", b"Wheel-Version: 1.0\n")
    flagged = bytearray(encrypted.getvalue())
    for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        start = 0
        while True:
            found = flagged.find(signature, start)
            if found < 0:
                break
            flagged[found + offset] |= 0x1
            start = found + 4
    _reject_bytes(tmp_path / "encrypted", bytes(flagged), "encrypted_entry")
    absolute = io.BytesIO()
    with zipfile.ZipFile(absolute, "w") as archive:
        archive.writestr("/tmp/evil", b"x")
    _reject_bytes(tmp_path / "absolute", absolute.getvalue(), "absolute_archive_path")
    travel = io.BytesIO()
    with zipfile.ZipFile(travel, "w") as archive:
        archive.writestr("../evil", b"x")
    _reject_bytes(tmp_path / "travel", travel.getvalue(), "archive_path_traversal")
    duplicate = io.BytesIO()
    with zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr("a.txt", b"1")
        archive.writestr("a.txt", b"2")
    _reject_bytes(tmp_path / "duplicate", duplicate.getvalue(), "duplicate_archive_member")
    colliding = io.BytesIO()
    with zipfile.ZipFile(colliding, "w") as archive:
        archive.writestr("A.txt", b"1")
        archive.writestr("a.txt", b"2")
    _reject_bytes(tmp_path / "case", colliding.getvalue(), "case_colliding_member")
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bomb", b"\0" * 200_000)
    _reject_bytes(tmp_path / "bomb", bomb.getvalue(), "excessive_compression_ratio")
    content = VERIFY.build_synthetic_wheel("demo", "1.0.0")
    limits = VERIFY.WheelLimits(max_member_uncompressed=8)
    _reject_bytes(tmp_path / "size", content, "excessive_uncompressed_size", limits=limits)
    _reject_bytes(
        tmp_path / "count",
        content,
        "excessive_member_count",
        limits=VERIFY.WheelLimits(max_members=1),
    )


def test_wheel_metadata_and_record_failures_are_rejected(tmp_path: Path) -> None:
    cases = [
        (VERIFY.build_synthetic_wheel("demo", "1.0.0", omit=frozenset({"METADATA"})), "missing_metadata"),
        (VERIFY.build_synthetic_wheel("demo", "1.0.0", omit=frozenset({"WHEEL"})), "missing_wheel_metadata"),
        (VERIFY.build_synthetic_wheel("demo", "1.0.0", omit=frozenset({"RECORD"})), "missing_record"),
        (VERIFY.build_synthetic_wheel("demo", "1.0.0", metadata_text="not metadata\n"), "malformed_metadata"),
        (VERIFY.build_synthetic_wheel("demo", "1.0.0", metadata_name="other"), "conflicting_package_name"),
        (VERIFY.build_synthetic_wheel("demo", "1.0.0", metadata_version="9.9.9"), "conflicting_package_version"),
        (VERIFY.build_synthetic_wheel("demo", "1.0.0", python_tag="cp312"), "incompatible_wheel_tag"),
        (
            VERIFY.build_synthetic_wheel(
                "demo",
                "1.0.0",
                record_digest_for={"demo-1.0.0.dist-info/WHEEL": "sha256=aaaa"},
            ),
            "record_hash_mismatch",
        ),
        (
            VERIFY.build_synthetic_wheel(
                "demo",
                "1.0.0",
                record_size_for={"demo-1.0.0.dist-info/WHEEL": "1"},
            ),
            "record_size_mismatch",
        ),
        (
            VERIFY.build_synthetic_wheel(
                "demo",
                "1.0.0",
                omit_from_record=frozenset({"demo-1.0.0.dist-info/WHEEL"}),
            ),
            "record_missing_member",
        ),
    ]
    for index, (content, reason) in enumerate(cases):
        _reject_bytes(tmp_path / str(index), content, reason)


def test_dependency_graph_failures_are_rejected(tmp_path: Path) -> None:
    missing = VERIFY.build_synthetic_wheel("demo", "1.0.0", requires_dist=["missingpkg"])
    _reject_bytes(tmp_path / "missing", missing, "missing_dependency")
    parent = VERIFY.build_synthetic_wheel("parent", "1.0.0", requires_dist=["child (>=2.0)"])
    child = VERIFY.build_synthetic_wheel("child", "1.0.0")
    packages = [
        _package(parent, "parent-1.0.0-py3-none-any.whl", requires=["child"]),
        _package(child, "child-1.0.0-py3-none-any.whl"),
    ]
    house = _house(
        tmp_path / "version",
        [("parent-1.0.0-py3-none-any.whl", parent), ("child-1.0.0-py3-none-any.whl", child)],
    )
    _expect(
        VERIFY.VerificationRejected,
        "unsatisfied_constraint",
        lambda: VERIFY.verify_wheelhouse(_manifest(packages), house),
    )
    extra = VERIFY.build_synthetic_wheel("demo", "1.0.0")
    _reject_bytes(tmp_path / "extra", extra, "missing_requested_extra", extras=["standard"])
    linux = VERIFY.build_synthetic_wheel("demo", "1.0.0", requires_dist=['onlylinux; sys_platform == "linux"'])
    _reject_bytes(tmp_path / "marker", linux, "missing_dependency")
    windows = VERIFY.build_synthetic_wheel("demo", "1.0.0", requires_dist=['onlywin; sys_platform == "win32"'])
    result = VERIFY.verify_wheelhouse(
        _manifest([_package(windows)]),
        _house(tmp_path / "windows", [(WHEEL, windows)]),
    )
    assert result["dependency_graph"] == "CONSISTENT_FOR_SYNTHETIC_SET"
    _reject_bytes(
        tmp_path / "python",
        VERIFY.build_synthetic_wheel("demo", "1.0.0", requires_python=">=3.13"),
        "incompatible_python",
    )
    omitted = VERIFY.build_synthetic_wheel("demo", "1.0.0", requires_dist=["child"])
    _reject_bytes(tmp_path / "omitted", omitted, "missing_dependency", requires=[])
    first = _package(VERIFY.build_synthetic_wheel("demo", "1.0.0"), "demo-1.0.0-py3-none-any.whl")
    second = _package(VERIFY.build_synthetic_wheel("demo", "1.0.0"), "demo-1.0.0-py3-none-any.whl")
    _expect(
        VERIFY.VerificationRejected,
        "duplicate_filename",
        lambda: VERIFY.verify_wheelhouse(_manifest([first, second]), tmp_path / "unused"),
    )
    other = _package(b"unused", "demo-2.0.0-py3-none-any.whl", version="2.0.0")
    _expect(
        VERIFY.VerificationRejected,
        "conflicting_versions",
        lambda: VERIFY.verify_wheelhouse(_manifest([first, other]), tmp_path / "unused-conflict"),
    )
    _expect(
        VERIFY.VerificationRejected,
        "missing_wheel",
        lambda: VERIFY.verify_wheelhouse(_manifest([first]), tmp_path / "empty-house"),
    )


def test_duplicate_normalized_package_is_rejected(tmp_path: Path) -> None:
    content = VERIFY.build_synthetic_wheel("demo", "1.0.0")
    first = _package(content, "demo-1.0.0-py3-none-any.whl")
    second = _package(content, "demo-1.0.0-py3-none-manylinux_2_28_x86_64.whl")
    _expect(
        VERIFY.VerificationRejected,
        "duplicate_package",
        lambda: VERIFY.verify_wheelhouse(_manifest([first, second]), tmp_path),
    )


def test_completion_claim_without_evidence_is_rejected(tmp_path: Path) -> None:
    content = VERIFY.build_synthetic_wheel("demo", "1.0.0")
    _expect(
        VERIFY.VerificationRejected,
        "false_completion_claim",
        lambda: VERIFY.verify_wheelhouse(
            _manifest([_package(content)], claimed_state="INDEPENDENT_ARTIFACT_VERIFICATION_COMPLETE"),
            tmp_path,
        ),
    )


def test_hash_zip_metadata_graph_and_provenance_are_separate(tmp_path: Path) -> None:
    _reject_bytes(tmp_path / "hash", b"not-a-zip", "malformed_zip")
    _reject_bytes(
        tmp_path / "meta",
        VERIFY.build_synthetic_wheel("demo", "1.0.0", metadata_text="not metadata\n"),
        "malformed_metadata",
    )
    _reject_bytes(
        tmp_path / "graph",
        VERIFY.build_synthetic_wheel("demo", "1.0.0", requires_dist=["missingpkg"]),
        "missing_dependency",
    )
    content = VERIFY.build_synthetic_wheel("demo", "1.0.0")
    house = _house(tmp_path / "prov", [(WHEEL, content)])
    _expect(
        VERIFY.VerificationRejected,
        "provenance_unverified",
        lambda: VERIFY.accept_verified_lock(_manifest([_package(content)]), house),
    )


def test_filesystem_boundaries_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _expect(ACQUIRE.DestinationRejected, "inside_repository", lambda: ACQUIRE.assert_destination_allowed(ROOT / "data"))
    _expect(
        ACQUIRE.DestinationRejected,
        "inside_onedrive",
        lambda: ACQUIRE.assert_destination_allowed(Path.home() / "OneDrive" / "not-created"),
    )
    _expect(ACQUIRE.DestinationRejected, "inside_staging_context", lambda: ACQUIRE.assert_destination_allowed(STAGING))
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "notes.txt").write_bytes(b"notes\n")
    _expect(ACQUIRE.DestinationRejected, "destination_not_empty", lambda: ACQUIRE.assert_destination_allowed(occupied))
    unexpected = tmp_path / "unexpected"
    unexpected.mkdir()
    (unexpected / "extra.whl").write_bytes(b"extra\n")
    _expect(ACQUIRE.DestinationRejected, "destination_not_empty", lambda: ACQUIRE.assert_destination_allowed(unexpected))
    linked = tmp_path / "linked"
    linked.mkdir()
    real = os.lstat

    def as_link(path: os.PathLike[str] | str) -> os.stat_result:
        if Path(path) == linked:
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0, st_nlink=1)  # type: ignore[return-value]
        return real(path)

    monkeypatch.setattr(ACQUIRE.os, "lstat", as_link)
    _expect(ACQUIRE.DestinationRejected, "symlink_or_reparse", lambda: ACQUIRE.assert_destination_allowed(linked))

    def as_reparse(path: os.PathLike[str] | str) -> os.stat_result:
        if Path(path) == linked:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400, st_nlink=1)  # type: ignore[return-value]
        return real(path)

    monkeypatch.setattr(ACQUIRE.os, "lstat", as_reparse)
    _expect(ACQUIRE.DestinationRejected, "symlink_or_reparse", lambda: ACQUIRE.assert_destination_allowed(linked))
    parent = tmp_path / "parent"
    parent.mkdir()
    child = parent / "wheelhouse"

    def parent_link(path: os.PathLike[str] | str) -> os.stat_result:
        if Path(path) == parent:
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0, st_nlink=1)  # type: ignore[return-value]
        return real(path)

    monkeypatch.setattr(ACQUIRE.os, "lstat", parent_link)
    _expect(ACQUIRE.DestinationRejected, "symlink_parent", lambda: ACQUIRE.assert_destination_allowed(child))
    monkeypatch.setattr(ACQUIRE.os, "lstat", real)
    _expect(
        ACQUIRE.DestinationRejected,
        "path_traversal",
        lambda: ACQUIRE.assert_destination_allowed(tmp_path / ".." / "outside"),
    )
    colliding = tmp_path / "colliding"
    colliding.mkdir()
    (colliding / "one.txt").write_bytes(b"one\n")
    monkeypatch.setattr(ACQUIRE, "_child_names", lambda _dest: ["A.whl", "a.whl"])
    _expect(ACQUIRE.DestinationRejected, "case_collision", lambda: ACQUIRE.assert_destination_allowed(colliding))
    monkeypatch.undo()
    empty = tmp_path / "exclusive"
    empty.mkdir()
    ACQUIRE.create_exclusive_file(empty, "demo.whl", b"synthetic")
    _expect(
        ACQUIRE.DestinationRejected,
        "unsafe_file_replacement",
        lambda: ACQUIRE.create_exclusive_file(empty, "demo.whl", b"replacement"),
    )
    _expect(
        ACQUIRE.AcquisitionRejected,
        "partial_download",
        lambda: ACQUIRE.assess_wheel_candidate(_candidate(partial=True)),
    )
    interrupted = tmp_path / "interrupted"
    interrupted.mkdir()
    real_write = os.write

    def short(descriptor: int, data: bytes) -> int:
        if len(data) > 1:
            real_write(descriptor, data[:1])
            return 1
        return real_write(descriptor, data)

    monkeypatch.setattr(ACQUIRE.os, "write", short)
    _expect(
        ACQUIRE.DestinationRejected,
        "interrupted_write",
        lambda: ACQUIRE.create_exclusive_file(interrupted, "demo.whl", b"synthetic"),
    )
    _expect(
        ACQUIRE.DestinationRejected,
        "sensitive_backup_filename",
        lambda: ACQUIRE.create_exclusive_file(tmp_path / "backup-name", "main example .env backup.txt", b"x"),
    )
    _expect(
        ACQUIRE.DestinationRejected,
        "operational_state_filename",
        lambda: ACQUIRE.create_exclusive_file(tmp_path / "ops-name", "live_safety_state.json", b"x"),
    )


def test_commit_does_not_open_a_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    plan = _prepare(tmp_path, "demo>=1", [_candidate()])
    assert plan["network_calls"] == 0
    assert plan["required_binary_argument"] == "--only-binary=:all:"
    assert plan["executed"] is False
    _expect(ACQUIRE.NetworkDisabled, "network_not_authorised", lambda: ACQUIRE.commit_acquisition(plan))


def test_markers_and_extras_are_preserved() -> None:
    row = INVENTORY.parse_requirement_line(
        'uvicorn[standard]>=0.27.0 ; sys_platform == "linux" and python_version >= "3.12"'
    )
    assert row["extras"] == ["standard"]
    assert row["environment_marker"] == 'sys_platform == "linux" and python_version >= "3.12"'
    assert INVENTORY.evaluate_marker(str(row["environment_marker"])) is True
