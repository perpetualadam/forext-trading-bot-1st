"""Offline end-to-end acquisition tests. No network and no real wheels."""

from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import os
import socket
import stat
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path
from types import SimpleNamespace

import pytest

CHILD = "g14-7-synthetic"
WHEEL_NAME = "demo-1.0.0-py3-none-any.whl"


def _load():
    path = Path(__file__).with_name("g14_7_transport.py")
    spec = importlib.util.spec_from_file_location("g14_7_transport_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("transport_missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


TRANSPORT = _load()
VERIFY = TRANSPORT._VERIFY
ACQUIRE = TRANSPORT._ACQUIRE


@pytest.fixture(autouse=True)
def deny_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("NETWORK_BOUNDARY_VIOLATION")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def _wheel(name: str = "demo", version: str = "1.0.0", **kwargs: object) -> bytes:
    return VERIFY.build_synthetic_wheel(name, version, **kwargs)


def _project(wheel: bytes, **overrides: object) -> dict[str, object]:
    filename = str(overrides.pop("filename", WHEEL_NAME))
    project: dict[str, object] = {
        "name": "demo",
        "version": "1.0.0",
        "filename": filename,
        "url": f"https://files.pythonhosted.org/packages/aa/{Path(filename).name}",
        "sha256": hashlib.sha256(wheel).hexdigest(),
        "size": len(wheel),
        "yanked": False,
        "requires": [],
        "provenance": "SYNTHETIC_TEST_ONLY",
        "kind": "wheel",
    }
    project.update(overrides)
    return project


def _document(projects: list[dict[str, object]]) -> dict[str, object]:
    return {"marker": "SYNTHETIC_TEST_ONLY", "projects": projects}


def _response(payload: bytes, content_type: str, **overrides: object) -> object:
    status = int(overrides.pop("status", 200))  # type: ignore[arg-type]
    return TRANSPORT.SyntheticResponse(
        status,
        chunks=tuple(overrides.pop("chunks", (payload,))),  # type: ignore[arg-type]
        content_length=overrides.pop("content_length", len(payload)),  # type: ignore[arg-type]
        content_type=str(overrides.pop("content_type", content_type)),
        location=overrides.pop("location", None),  # type: ignore[arg-type]
        complete=bool(overrides.pop("complete", True)),
        elapsed_ms=int(overrides.pop("elapsed_ms", 0)),  # type: ignore[arg-type]
        headers_size=int(overrides.pop("headers_size", 0)),  # type: ignore[arg-type]
    )


def _index(document: dict[str, object]) -> object:
    payload = TRANSPORT._canonical(document).encode("utf-8")
    return _response(payload, TRANSPORT.INDEX_CONTENT_TYPE)


def _redirect(location: str) -> object:
    return TRANSPORT.SyntheticResponse(302, location=location)


def _artifact(wheel: bytes, filename: str) -> list[object]:
    location = f"https://files.pythonhosted.org/packages/bb/{Path(filename).name}"
    return [_redirect(location), _response(wheel, TRANSPORT.WHEEL_CONTENT_TYPE)]


def _bundle(projects: list[tuple[bytes, dict[str, object]]]) -> tuple[dict[str, object], list[object]]:
    document = _document([project for _wheel_bytes, project in projects])
    responses = [_index(document)]
    for wheel, project in projects:
        responses.extend(_artifact(wheel, str(project["filename"])))
    return document, responses


def _valid() -> tuple[dict[str, object], list[object]]:
    wheel = _wheel()
    return _bundle([(wheel, _project(wheel))])


def _run(tmp_path: Path, document: dict[str, object], responses: list[object], **kwargs: object) -> dict[str, object]:
    transport = TRANSPORT.ScriptedTransport(responses)
    workflow = TRANSPORT.AcquisitionWorkflow(transport)
    result = workflow.run(
        requirements_text=str(kwargs.pop("requirements_text", "demo==1.0.0\n")),
        index_document=document,
        destination_parent=Path(str(kwargs.pop("destination_parent", tmp_path))),
        index_url=str(kwargs.pop("index_url", ACQUIRE.PROPOSED_INDEX_URL)),
        extra_indexes=tuple(kwargs.pop("extra_indexes", ())),  # type: ignore[arg-type]
        read_transform=kwargs.pop("read_transform", None),  # type: ignore[arg-type]
        before_write=kwargs.pop("before_write", None),  # type: ignore[arg-type]
    )
    result["requests"] = len(transport.requests)
    return result


def _fail(tmp_path: Path, reason: str, document: dict[str, object], responses: list[object], **kwargs: object) -> object:
    transport = TRANSPORT.ScriptedTransport(responses)
    workflow = TRANSPORT.AcquisitionWorkflow(transport)
    with pytest.raises(TRANSPORT.WorkflowRejected) as caught:
        workflow.run(
            requirements_text=str(kwargs.pop("requirements_text", "demo==1.0.0\n")),
            index_document=document,
            destination_parent=Path(str(kwargs.pop("destination_parent", tmp_path))),
            index_url=str(kwargs.pop("index_url", ACQUIRE.PROPOSED_INDEX_URL)),
            read_transform=kwargs.pop("read_transform", None),  # type: ignore[arg-type]
            before_write=kwargs.pop("before_write", None),  # type: ignore[arg-type]
        )
    assert caught.value.reason == reason
    assert workflow.state == "FAILED_CLOSED"
    return transport


def _symlink(source: Path, link: Path) -> None:
    try:
        os.symlink(source, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"NOT_EXECUTED_WITH_REASON: symlink_unavailable:{exc.errno}")


def test_network_guard_blocks_connect() -> None:
    with pytest.raises(AssertionError, match="NETWORK_BOUNDARY_VIOLATION"):
        socket.socket().connect(("127.0.0.1", 9))


def test_sources_do_not_import_a_network_client() -> None:
    banned = ("import socket", "import urllib", "import requests", "import httpx", "import subprocess", "import docker")
    for name in ("g14_7_transport.py", "g14_7_fs.py"):
        text = Path(__file__).with_name(name).read_text(encoding="utf-8")
        for token in banned:
            assert token not in text
    assert TRANSPORT.NETWORK_ENABLED is False
    assert TRANSPORT.DEFAULT_TRANSPORT == "NETWORK_DISABLED"


def test_end_to_end_complete_synthetic(tmp_path: Path) -> None:
    document, responses = _valid()
    result = _run(tmp_path, document, responses)
    assert result["state"] == "COMPLETE_SYNTHETIC"
    assert result["network_calls"] == 0
    assert result["real_dependency_lock_created"] is False
    assert result["real_wheelhouse_acquired"] is False
    assert result["filesystem_race_status"] == "ACQUISITION_FILESYSTEM_BOUNDARY_UNVERIFIED"
    assert "SYNTHETIC_TEST_ONLY" in str(result["lock"])
    assert result["lock"]["source"]["source_approved"] is False
    assert result["lock"]["source"]["index_url"] == "synthetic://fixture"
    names = sorted(path.name for path in (tmp_path / CHILD).iterdir())
    assert names == [WHEEL_NAME, "synthetic-lock.json"]


@pytest.mark.parametrize(
    ("reason", "mutate"),
    [
        ("unapproved_host", "index"),
        ("unexpected_artifact_host", "artifact-host"),
        ("https_downgrade", "downgrade"),
        ("cross_host_redirect", "third-host"),
        ("excessive_redirects", "redirects"),
        ("unexpected_status", "status"),
        ("timeout", "timeout"),
        ("retry_exhausted", "retry"),
        ("oversized_response", "oversize"),
        ("truncated_response", "truncated"),
        ("missing_artifact", "missing"),
        ("source_distribution", "sdist"),
        ("yanked_release", "yanked"),
        ("unapproved_prerelease", "prerelease"),
        ("unsupported_wheel_tag", "tag"),
        ("hash_mismatch", "hash"),
        ("size_mismatch", "size"),
        ("malformed_zip", "zip"),
        ("missing_wheel_metadata", "wheel-meta"),
        ("missing_metadata", "metadata"),
        ("missing_record", "record"),
        ("missing_dependency", "dependency"),
        ("incorrect_environment_marker", "marker"),
        ("missing_requested_extra", "extra"),
        ("interrupted_stream", "interrupted"),
        ("duplicate_filename", "duplicate"),
        ("case_collision", "case"),
        ("false_completion_claim", "provenance"),
        ("path_traversal", "relative"),
        ("path_traversal", "absolute"),
        ("sensitive_backup_filename", "backup"),
        ("operational_state_filename", "operational-name"),
        ("destination_not_empty", "nonempty"),
        ("destination_not_empty", "manifest"),
        ("destination_exists", "repeat-empty"),
        ("inside_repository", "repo"),
        ("inside_onedrive", "onedrive"),
        ("inside_staging_context", "staging"),
        ("inside_consensus_forecast", "consensus"),
        ("operational_state_path", "shadow"),
    ],
)
def test_failure_injection(tmp_path: Path, reason: str, mutate: str) -> None:
    document, responses = _prepare(tmp_path, mutate)
    parent = _parent(tmp_path, mutate)
    requirements = _requirements(mutate)
    _fail(tmp_path, reason, document, responses, destination_parent=parent, requirements_text=requirements, index_url=_index_url(mutate))
    if mutate == "manifest":
        assert (tmp_path / CHILD / "synthetic-lock.json").read_bytes() == b"{}"


def _index_url(mutate: str) -> str:
    if mutate == "index":
        return "https://evil.example/simple"
    return ACQUIRE.PROPOSED_INDEX_URL


def _requirements(mutate: str) -> str:
    if mutate == "marker":
        return 'demo==1.0.0; sys_platform == "win32"\n'
    if mutate == "extra":
        return "demo[fast]==1.0.0\n"
    if mutate == "case":
        return "demo==1.0.0\n"
    return "demo==1.0.0\n"


def _parent(tmp_path: Path, mutate: str) -> Path:
    if mutate == "repo":
        return ACQUIRE.REPO
    if mutate == "onedrive":
        return Path(r"C:\Users\Brian\OneDrive\g14-7-denied")
    if mutate == "staging":
        return ACQUIRE.STAGING
    if mutate == "consensus":
        return Path(r"C:\synthetic\concensus-forecast")
    if mutate == "shadow":
        return Path(r"C:\synthetic\shadow_state")
    if mutate == "nonempty":
        dest = tmp_path / CHILD
        dest.mkdir()
        (dest / "stray.txt").write_bytes(b"stray")
    if mutate == "manifest":
        dest = tmp_path / CHILD
        dest.mkdir()
        (dest / "synthetic-lock.json").write_bytes(b"{}")
    if mutate == "repeat-empty":
        (tmp_path / CHILD).mkdir()
    return tmp_path


def _prepare(tmp_path: Path, mutate: str) -> tuple[dict[str, object], list[object]]:
    wheel = _wheel()
    project = _project(wheel)
    if mutate == "artifact-host":
        project["url"] = "https://evil.example/demo-1.0.0-py3-none-any.whl"
    elif mutate == "sdist":
        project["filename"] = "demo-1.0.0.tar.gz"
        project["kind"] = "sdist"
        project["url"] = "https://files.pythonhosted.org/packages/aa/demo-1.0.0.tar.gz"
    elif mutate == "yanked":
        project["yanked"] = True
    elif mutate == "prerelease":
        project["version"] = "1.0.0a1"
        project["filename"] = "demo-1.0.0a1-py3-none-any.whl"
        project["url"] = "https://files.pythonhosted.org/packages/aa/demo-1.0.0a1-py3-none-any.whl"
    elif mutate == "tag":
        project["filename"] = "demo-1.0.0-py3-cp39-any.whl"
        project["url"] = "https://files.pythonhosted.org/packages/aa/demo-1.0.0-py3-cp39-any.whl"
    elif mutate == "hash":
        project["sha256"] = "0" * 64
    elif mutate == "size":
        project["size"] = len(wheel) + 1
    elif mutate == "dependency":
        wheel = _wheel(requires_dist=["other==1.0.0"])
        project = _project(wheel, requires=["other"])
    elif mutate == "duplicate":
        second = dict(project)
        document = _document([project, second])
        return document, [_index(document)]
    elif mutate == "case":
        other = _project(wheel, filename="Demo-1.0.0-py3-none-any.whl")
        document = _document([project, other])
        return document, [_index(document)]
    elif mutate == "provenance":
        project["provenance"] = "production"
    elif mutate == "relative":
        project["filename"] = "../escape.whl"
    elif mutate == "absolute":
        project["filename"] = "C:/outside.whl"
    elif mutate == "backup":
        project["filename"] = "main example .env backup.txt"
    elif mutate == "operational-name":
        project["filename"] = "live_safety_state.json"
    elif mutate == "zip":
        wheel = b"this is not a zip archive"
        project = _project(wheel)
    elif mutate == "wheel-meta":
        wheel = _wheel(omit=frozenset({"WHEEL"}))
        project = _project(wheel)
    elif mutate == "metadata":
        wheel = _wheel(omit=frozenset({"METADATA"}))
        project = _project(wheel)
    elif mutate == "record":
        wheel = _wheel(omit=frozenset({"RECORD"}))
        project = _project(wheel)
    document = _document([project])
    responses: list[object] = [_index(document)]
    if mutate == "downgrade":
        responses.append(_redirect("http://files.pythonhosted.org/packages/bb/" + WHEEL_NAME))
    elif mutate == "third-host":
        responses.append(_redirect("https://evil.example/" + WHEEL_NAME))
    elif mutate == "redirects":
        for label in ("bb", "cc", "dd"):
            responses.append(_redirect(f"https://files.pythonhosted.org/packages/{label}/{WHEEL_NAME}"))
    elif mutate == "status":
        responses.append(TRANSPORT.SyntheticResponse(500))
    elif mutate == "timeout":
        responses.append(_response(wheel, TRANSPORT.WHEEL_CONTENT_TYPE, elapsed_ms=TRANSPORT.TIMEOUT_MS + 1))
    elif mutate == "retry":
        responses.extend(TRANSPORT.SyntheticResponse(503) for _ in range(3))
    elif mutate == "oversize":
        chunk = b"x" * (TRANSPORT.MAX_CHUNK_BYTES + 1)
        responses.append(_response(b"", TRANSPORT.WHEEL_CONTENT_TYPE, chunks=(chunk,), content_length=len(chunk)))
    elif mutate == "truncated":
        responses.append(_response(b"short", TRANSPORT.WHEEL_CONTENT_TYPE, content_length=50))
    elif mutate == "interrupted":
        responses.append(_response(wheel, TRANSPORT.WHEEL_CONTENT_TYPE, complete=False))
    elif mutate == "missing":
        pass
    elif mutate in {"hash", "size", "zip", "wheel-meta", "metadata", "record", "dependency", "extra"}:
        responses.extend(_artifact(wheel, str(project["filename"])))
    elif mutate in {"index", "artifact-host", "sdist", "yanked", "prerelease", "tag", "duplicate", "case", "provenance", "relative", "absolute", "backup", "operational-name", "nonempty", "manifest", "repeat-empty", "repo", "onedrive", "staging", "consensus", "shadow"}:
        pass
    else:
        responses.extend(_artifact(wheel, str(project["filename"])))
    return document, responses


def test_conflicting_dependency(tmp_path: Path) -> None:
    demo = _wheel("demo", "1.0.0", requires_dist=["other==2.0.0"])
    other = _wheel("other", "1.0.0")
    first = _project(demo, requires=["other"])
    second = _project(
        other,
        name="other",
        filename="other-1.0.0-py3-none-any.whl",
        url="https://files.pythonhosted.org/packages/aa/other-1.0.0-py3-none-any.whl",
    )
    document, responses = _bundle([(demo, first), (other, second)])
    _fail(tmp_path, "unsatisfied_constraint", document, responses, requirements_text="demo==1.0.0\nother==1.0.0\n")


def test_missing_transport(tmp_path: Path) -> None:
    document, _responses = _valid()
    workflow = TRANSPORT.AcquisitionWorkflow(None)
    with pytest.raises(TRANSPORT.WorkflowRejected) as caught:
        workflow.run(requirements_text="demo==1.0.0\n", index_document=document, destination_parent=tmp_path)
    assert caught.value.reason == "missing_transport"
    assert workflow.state == "FAILED_CLOSED"


def test_real_network_fallback_is_rejected(tmp_path: Path) -> None:
    document, _responses = _valid()

    class Hostile:
        def exchange(self, _request: object) -> object:
            socket.create_connection(("127.0.0.1", 9))
            return TRANSPORT.SyntheticResponse(200)

    workflow = TRANSPORT.AcquisitionWorkflow(Hostile())  # type: ignore[arg-type]
    with pytest.raises(TRANSPORT.WorkflowRejected) as caught:
        workflow.run(requirements_text="demo==1.0.0\n", index_document=document, destination_parent=tmp_path)
    assert caught.value.reason == "real_network_fallback"
    assert workflow.state == "FAILED_CLOSED"


@pytest.mark.parametrize(
    "method_name",
    ["declare_fetch", "declare_verified", "declare_graph", "declare_lock", "declare_complete"],
)
def test_out_of_order_transition(method_name: str) -> None:
    workflow = TRANSPORT.AcquisitionWorkflow(TRANSPORT.ScriptedTransport([]))
    with pytest.raises(TRANSPORT.WorkflowRejected) as caught:
        getattr(workflow, method_name)()
    assert caught.value.reason == "illegal_transition"
    assert workflow.state == "FAILED_CLOSED"


def test_manifest_tamper_fails_closed(tmp_path: Path) -> None:
    document, responses = _valid()

    def flip(_name: str, data: bytes) -> bytes:
        return b"\x00" + data[1:]

    _fail(tmp_path, "hash_mismatch", document, responses, read_transform=flip)


def test_partial_write_is_not_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def short(_handle: int, _buffer: object, _count: int, written: object, _overlapped: object) -> int:
        ctypes.cast(written, ctypes.POINTER(wintypes.DWORD))[0] = 0
        return 1

    monkeypatch.setattr(TRANSPORT._FS._KERNEL, "WriteFile", short)
    document, responses = _valid()
    _fail(tmp_path, "interrupted_write", document, responses)
    assert (tmp_path / CHILD).is_dir()
    assert not (tmp_path / CHILD / "synthetic-lock.json").exists()


def test_parent_replacement_does_not_redirect(tmp_path: Path) -> None:
    document, responses = _valid()

    def swap(_handle: object) -> None:
        original = tmp_path / CHILD
        original.rename(tmp_path / "bound-original")
        (tmp_path / CHILD).mkdir()

    result = _run(tmp_path, document, responses, before_write=swap)
    assert result["state"] == "COMPLETE_SYNTHETIC"
    assert list((tmp_path / CHILD).iterdir()) == []
    bound = tmp_path / "bound-original"
    assert (bound / WHEEL_NAME).is_file()
    assert (bound / "synthetic-lock.json").is_file()


def test_hard_link_substitution_rejected(tmp_path: Path) -> None:
    document, responses = _valid()
    seed = tmp_path / "seed"
    seed.write_bytes(b"seed")

    def link(_handle: object) -> None:
        try:
            os.link(seed, tmp_path / CHILD / WHEEL_NAME)
        except OSError as exc:
            pytest.skip(f"NOT_EXECUTED_WITH_REASON: hard_link_unavailable:{exc.errno}")

    _fail(tmp_path, "unsafe_file_replacement", document, responses, before_write=link)


def test_destination_symlink_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    _symlink(target, tmp_path / CHILD)
    document, responses = _valid()
    _fail(tmp_path, "symlink_or_reparse", document, responses)


def test_parent_symlink_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    (real / "inner").mkdir(parents=True)
    link = tmp_path / "link"
    _symlink(real, link)
    document, responses = _valid()
    _fail(tmp_path, "symlink_parent", document, responses, destination_parent=link / "inner")


def _fake_link() -> SimpleNamespace:
    return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0, st_nlink=1)


def test_injected_destination_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / CHILD
    dest.mkdir()
    original = ACQUIRE.os.lstat

    def fake(path: object) -> object:
        if Path(str(path)) == dest:
            return _fake_link()
        return original(path)

    monkeypatch.setattr(ACQUIRE.os, "lstat", fake)
    document, responses = _valid()
    _fail(tmp_path, "symlink_or_reparse", document, responses)


def test_injected_parent_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = ACQUIRE.os.lstat

    def fake(path: object) -> object:
        if Path(str(path)) == tmp_path.parent:
            return _fake_link()
        return original(path)

    monkeypatch.setattr(ACQUIRE.os, "lstat", fake)
    document, responses = _valid()
    _fail(tmp_path, "symlink_parent", document, responses)


def test_injected_reparse_point(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / CHILD
    dest.mkdir()
    original = ACQUIRE.os.lstat

    def fake(path: object) -> object:
        if Path(str(path)) == dest:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400, st_nlink=1)
        return original(path)

    monkeypatch.setattr(ACQUIRE.os, "lstat", fake)
    document, responses = _valid()
    _fail(tmp_path, "symlink_or_reparse", document, responses)


def test_junction_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "junction"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip("NOT_EXECUTED_WITH_REASON: junction_creation_unavailable")
    document, responses = _valid()
    _fail(tmp_path, "symlink_or_reparse", document, responses, destination_parent=link)


def test_repeated_acquisition_rejected(tmp_path: Path) -> None:
    document, responses = _valid()
    _run(tmp_path, document, list(responses))
    _fail(tmp_path, "destination_not_empty", document, list(responses))


def test_prohibited_destinations_are_not_created() -> None:
    assert not (ACQUIRE.REPO / CHILD).exists()
    assert not Path(r"C:\synthetic\concensus-forecast").exists()
