"""Offline acquisition workflow. The default transport cannot use a network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

NETWORK_ENABLED = False
DEFAULT_TRANSPORT = "NETWORK_DISABLED"
MAX_ARTIFACT_BYTES = 1_048_576
MAX_TOTAL_BYTES = 4_194_304
MAX_HEADER_BYTES = 8_192
MAX_CHUNK_BYTES = 65_536
MAX_RETRIES = 2
TIMEOUT_MS = 5_000
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
RETRYABLE_STATUSES = frozenset({503})
INDEX_CONTENT_TYPE = "application/vnd.g14-synthetic-index+json"
WHEEL_CONTENT_TYPE = "application/octet-stream"
CHILD_NAME = "g14-7-synthetic"
LOCK_NAME = "synthetic-lock.json"
SYNTHETIC_MARKER = "SYNTHETIC_TEST_ONLY"
POST_OPEN_BINDING = "POST_OPEN_DIRECTORY_HANDLE_BOUND"
INITIAL_LOOKUP = "INITIAL_PATH_LOOKUP_NOT_ATOMIC"
RACE_CLASSIFICATION = "ACQUISITION_FILESYSTEM_BOUNDARY_UNVERIFIED"
STATES = (
    "CREATED",
    "POLICY_VALIDATED",
    "TARGET_VALIDATED",
    "RESOLUTION_VALIDATED",
    "DESTINATION_VALIDATED",
    "FETCHING_SYNTHETIC",
    "ARTIFACTS_RECEIVED",
    "ARTIFACTS_VERIFIED",
    "DEPENDENCY_GRAPH_VERIFIED",
    "SYNTHETIC_LOCK_PREPARED",
    "COMPLETE_SYNTHETIC",
    "FAILED_CLOSED",
)
TARGET_PROFILE = {
    "os": "linux",
    "arch": "x86_64",
    "implementation": "cp",
    "python_major_minor": "3.12",
    "python_patch": "UNKNOWN",
    "soabi": "UNKNOWN",
    "glibc": "UNKNOWN",
    "pip_version": "UNKNOWN",
    "native_wheel_tags": "UNKNOWN",
    "native_compatibility": "UNVERIFIED",
}


class WorkflowRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TransportError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SyntheticRequest:
    def __init__(self, url: str, role: str, timeout_ms: int) -> None:
        self.url = url
        self.role = role
        self.timeout_ms = timeout_ms


class SyntheticResponse:
    def __init__(
        self,
        status: int,
        *,
        chunks: tuple[bytes, ...] = (),
        content_length: int | None = None,
        content_type: str = "",
        location: str | None = None,
        complete: bool = True,
        elapsed_ms: int = 0,
        headers_size: int = 0,
    ) -> None:
        self.status = status
        self.chunks = chunks
        self.content_length = content_length
        self.content_type = content_type
        self.location = location
        self.complete = complete
        self.elapsed_ms = elapsed_ms
        self.headers_size = headers_size


class ScriptedTransport:
    """In-memory responses. This object has no socket and no network client."""

    def __init__(self, responses: tuple[SyntheticResponse, ...] | list[SyntheticResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[SyntheticRequest] = []

    def exchange(self, request: SyntheticRequest) -> SyntheticResponse:
        self.requests.append(request)
        if not self._responses:
            raise TransportError("missing_artifact")
        return self._responses.pop(0)


def _load(stem: str) -> Any:
    path = Path(__file__).with_name(f"{stem}.py")
    name = f"{stem}_for_g147"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise WorkflowRejected("helper_missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_ACQUIRE = _load("g14_4_acquire")
_VERIFY = _load("g14_4_verify")
_INVENTORY = _load("g14_4_inventory")
_FS = _load("g14_7_fs")


class AcquisitionWorkflow:
    """One synthetic acquisition. Omitting the transport fails closed."""

    def __init__(self, transport: ScriptedTransport | None) -> None:
        self.transport = transport
        self.state = "CREATED"
        self.evidence: dict[str, Any] = {}
        self.lock_document: dict[str, Any] | None = None
        self._rows: list[dict[str, Any]] = []
        self._projects: list[dict[str, Any]] = []
        self._parent: Path | None = None
        self._dest: Path | None = None
        self._parent_handle: Any = None
        self._dest_handle: Any = None
        self._file_handles: list[int] = []
        self._members: dict[str, bytes] = {}
        self._read_transform: Callable[[str, bytes], bytes] | None = None
        self._before_write: Callable[[Any], None] | None = None
        self._closed = False

    def run(
        self,
        *,
        requirements_text: str,
        index_document: dict[str, Any],
        destination_parent: Path,
        index_url: str = _ACQUIRE.PROPOSED_INDEX_URL,
        target: dict[str, str] | None = None,
        inherited: dict[str, str] | None = None,
        extra_indexes: tuple[str, ...] = (),
        read_transform: Callable[[str, bytes], bytes] | None = None,
        before_write: Callable[[Any], None] | None = None,
    ) -> dict[str, Any]:
        self._read_transform = read_transform
        self._before_write = before_write
        try:
            self._require_synthetic_transport()
            self._validate_policy(index_url, inherited or {}, extra_indexes)
            self._validate_target(target or dict(TARGET_PROFILE))
            self._validate_resolution(requirements_text, index_document)
            self._validate_destination(destination_parent)
            self._fetch(index_url, index_document)
            self._verify()
            self._prepare_lock()
            return self._complete()
        except WorkflowRejected:
            self.state = "FAILED_CLOSED"
            raise
        finally:
            self._close()

    def declare_fetch(self) -> None:
        self._advance("DESTINATION_VALIDATED", "FETCHING_SYNTHETIC")

    def declare_verified(self) -> None:
        self._advance("ARTIFACTS_RECEIVED", "ARTIFACTS_VERIFIED")

    def declare_graph(self) -> None:
        self._advance("ARTIFACTS_VERIFIED", "DEPENDENCY_GRAPH_VERIFIED")

    def declare_lock(self) -> None:
        self._advance("DEPENDENCY_GRAPH_VERIFIED", "SYNTHETIC_LOCK_PREPARED")

    def declare_complete(self) -> None:
        if self.state != "SYNTHETIC_LOCK_PREPARED":
            self._fail("illegal_transition")
        if self.lock_document is None or SYNTHETIC_MARKER not in json.dumps(self.lock_document):
            self._fail("incomplete_evidence")
        self.state = "COMPLETE_SYNTHETIC"

    def _require_synthetic_transport(self) -> None:
        if NETWORK_ENABLED:
            self._fail("real_network_fallback")
        if self.transport is None:
            self._fail("missing_transport")
        if type(self.transport) is not ScriptedTransport:
            self._fail("real_network_fallback")

    def _validate_policy(self, index_url: str, inherited: dict[str, str], extra_indexes: tuple[str, ...]) -> None:
        self._advance("CREATED", "POLICY_VALIDATED")
        self._call(lambda: _ACQUIRE.authorize_url(index_url, role="index"))
        self._call(lambda: _ACQUIRE.reject_additional_indexes(extra_indexes))
        self._call(
            lambda: _ACQUIRE.build_acquisition_environment(
                inherited,
                interpreter=Path(r"C:\synthetic\python.exe"),
                platform_basics={"SYSTEMROOT": r"C:\synthetic\windows", "WINDIR": r"C:\synthetic\windows"},
            )
        )

    def _validate_target(self, target: dict[str, str]) -> None:
        self._advance("POLICY_VALIDATED", "TARGET_VALIDATED")
        required = ("os", "arch", "implementation", "python_major_minor")
        for key in required:
            if target.get(key) != TARGET_PROFILE[key]:
                self._fail("target_rejected")
        for key in ("python_patch", "soabi", "glibc", "pip_version", "native_wheel_tags"):
            if target.get(key) != "UNKNOWN":
                self._fail("target_profile_not_invented")
        if target.get("native_compatibility") == "VERIFIED":
            self._fail("native_platform_unverified")
        self.evidence["target"] = {
            "os": "linux",
            "arch": "x86_64",
            "implementation": "cp",
            "python_major_minor": "3.12",
            "python_patch": "UNKNOWN",
            "soabi": "UNKNOWN",
            "glibc": "UNKNOWN",
            "native_wheel_tags": "UNKNOWN",
            "classification": "TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE",
        }

    def _validate_resolution(self, requirements_text: str, index_document: dict[str, Any]) -> None:
        self._advance("TARGET_VALIDATED", "RESOLUTION_VALIDATED")
        if index_document.get("marker") != SYNTHETIC_MARKER:
            self._fail("synthetic_fixture_unmarked")
        rows = self._call(lambda: _INVENTORY.parse_requirement_document(requirements_text))
        projects = index_document.get("projects")
        if not isinstance(projects, list) or not projects:
            self._fail("missing_artifact")
        expected = {str(row["normalized_name"]): row for row in rows}
        selected: dict[str, str] = {}
        names: list[str] = []
        for project in projects:
            if not isinstance(project, dict):
                self._fail("missing_artifact")
            if project.get("provenance") != SYNTHETIC_MARKER:
                self._fail("false_completion_claim")
            filename = str(project.get("filename", ""))
            self._invoke(_ACQUIRE.reject_member_name, filename)
            self._invoke(_ACQUIRE.assess_wheel_candidate, project)
            normalized = _INVENTORY.normalize_name(str(project.get("name", "")))
            if normalized not in expected:
                self._fail("unexpected_package")
            version = str(project.get("version", ""))
            if normalized in selected and selected[normalized] != version:
                self._fail("conflicting_versions")
            marker = expected[normalized]["environment_marker"]
            if marker is not None:
                outcome = self._invoke(_INVENTORY.evaluate_marker, marker)
                if outcome is None:
                    self._fail("marker_unverified")
                if outcome is False:
                    self._fail("incorrect_environment_marker")
            selected[normalized] = version
            names.append(filename)
        self._call(lambda: _ACQUIRE.reject_case_colliding_names(names))
        folded = [name.casefold() for name in names]
        if len(folded) != len(set(folded)):
            self._fail("duplicate_filename")
        if set(expected) - set(selected):
            self._fail("missing_wheel")
        self._rows = rows
        self._projects = [dict(project) for project in projects]

    def _validate_destination(self, parent: Path) -> None:
        self._advance("RESOLUTION_VALIDATED", "DESTINATION_VALIDATED")
        destination = parent / CHILD_NAME
        self._call(lambda: _ACQUIRE.assert_destination_boundary(parent))
        self._call(lambda: _ACQUIRE.assert_destination_boundary(destination))
        if destination.exists():
            self._call(lambda: _ACQUIRE.assert_destination_allowed(destination))
            self._fail("destination_exists")
        parent_handle = self._call(lambda: _FS.open_directory(parent))
        self._parent_handle = parent_handle
        self._dest_handle = self._call(lambda: parent_handle.create_directory(CHILD_NAME))
        self._parent = parent
        self._dest = destination

    def _fetch(self, index_url: str, index_document: dict[str, Any]) -> None:
        self._advance("DESTINATION_VALIDATED", "FETCHING_SYNTHETIC")
        self._require_synthetic_transport()
        confirmation = self._request(index_url, "index", INDEX_CONTENT_TYPE, MAX_HEADER_BYTES)
        if confirmation != _canonical(index_document).encode("utf-8"):
            self._fail("index_mismatch")
        total = 0
        received: dict[str, bytes] = {}
        for project in self._projects:
            url = str(project["url"])
            body = self._request(url, "artifact", WHEEL_CONTENT_TYPE, int(project["size"]))
            digest = hashlib.sha256(body).hexdigest()
            if digest != project["sha256"]:
                self._fail("hash_mismatch")
            if len(body) != int(project["size"]):
                self._fail("size_mismatch")
            total += len(body)
            if total > MAX_TOTAL_BYTES:
                self._fail("oversized_response")
            received[str(project["filename"])] = body
        if self._before_write is not None and self._dest_handle is not None:
            self._before_write(self._dest_handle)
        for name, body in received.items():
            handle = self._invoke(self._dest_handle.write_exclusive, name, body)
            self._file_handles.append(handle)
            size = len(body)
            read_back = self._invoke(self._dest_handle.read_existing, handle, size)
            if self._read_transform is not None:
                read_back = self._read_transform(name, read_back)
            self._members[name] = read_back
        self._advance("FETCHING_SYNTHETIC", "ARTIFACTS_RECEIVED")

    def _verify(self) -> None:
        self._advance("ARTIFACTS_RECEIVED", "ARTIFACTS_VERIFIED")
        manifest = self._lock_body()
        result = self._call(lambda: _VERIFY.verify_member_bytes(manifest, dict(self._members)))
        if result.get("dependency_graph") != "CONSISTENT_FOR_SYNTHETIC_SET":
            self._fail("graph_validation_failed")
        if result.get("real_dependency_lock_created") != "false":
            self._fail("false_completion_claim")
        self.evidence["verification"] = result
        self._advance("ARTIFACTS_VERIFIED", "DEPENDENCY_GRAPH_VERIFIED")

    def _prepare_lock(self) -> None:
        self._advance("DEPENDENCY_GRAPH_VERIFIED", "SYNTHETIC_LOCK_PREPARED")
        document = self._lock_body()
        if document["source"]["source_approved"] is not False:
            self._fail("false_completion_claim")
        if SYNTHETIC_MARKER not in json.dumps(document):
            self._fail("synthetic_marker_missing")
        payload = _canonical(document).encode("utf-8")
        handle = self._call(lambda: self._dest_handle.write_exclusive(LOCK_NAME, payload))
        self._file_handles.append(handle)
        read_back = self._call(lambda: self._dest_handle.read_existing(handle, len(payload)))
        if read_back != payload:
            self._fail("partial_download")
        self.lock_document = document

    def _complete(self) -> dict[str, Any]:
        self.declare_complete()
        expected = {str(project["filename"]) for project in self._projects}
        expected.add(LOCK_NAME)
        if set(self._dest_handle.names) != expected:
            self._fail("unexpected_file")
        return {
            "state": self.state,
            "lock": self.lock_document,
            "network_calls": 0,
            "synthetic_exchanges": len(self.transport.requests) if isinstance(self.transport, ScriptedTransport) else 0,
            "filesystem_race_status": RACE_CLASSIFICATION,
            "post_open_binding": POST_OPEN_BINDING,
            "initial_lookup": INITIAL_LOOKUP,
            "real_dependency_lock_created": False,
            "real_wheelhouse_acquired": False,
        }

    def _request(self, url: str, role: str, content_type: str, declared_size: int) -> bytes:
        assert isinstance(self.transport, ScriptedTransport)
        chain = [url]
        redirects = 0
        retries = 0
        while True:
            current = chain[-1]
            self._call(lambda: _ACQUIRE.authorize_redirect_chain(list(chain), role=role))
            request = SyntheticRequest(current, role, TIMEOUT_MS)
            try:
                response = self.transport.exchange(request)
            except TransportError as exc:
                self._fail(exc.reason)
            if response.elapsed_ms > TIMEOUT_MS:
                self._fail("timeout")
            if response.headers_size > MAX_HEADER_BYTES:
                self._fail("oversized_headers")
            if response.status in RETRYABLE_STATUSES:
                retries += 1
                if retries > MAX_RETRIES:
                    self._fail("retry_exhausted")
                continue
            if response.status in REDIRECT_STATUSES:
                if not response.location:
                    self._fail("unapproved_redirect")
                redirects += 1
                if redirects > _ACQUIRE.MAX_REDIRECTS:
                    self._fail("excessive_redirects")
                chain.append(response.location)
                continue
            if response.status != 200:
                self._fail("unexpected_status")
            if response.content_type != content_type:
                self._fail("unexpected_content_type")
            return self._bounded(response, declared_size)

    def _bounded(self, response: SyntheticResponse, declared_size: int) -> bytes:
        if declared_size > MAX_ARTIFACT_BYTES or (response.content_length or 0) > MAX_ARTIFACT_BYTES:
            self._fail("oversized_response")
        if not response.complete:
            self._fail("interrupted_stream")
        collected = bytearray()
        for chunk in response.chunks:
            if len(chunk) > MAX_CHUNK_BYTES:
                self._fail("oversized_response")
            if len(collected) + len(chunk) > MAX_ARTIFACT_BYTES:
                self._fail("oversized_response")
            collected.extend(chunk)
        if response.content_length is not None and response.content_length != len(collected):
            if response.content_length > len(collected):
                self._fail("truncated_response")
            self._fail("conflicting_size")
        if not collected:
            self._fail("truncated_response")
        return bytes(collected)

    def _lock_body(self) -> dict[str, Any]:
        packages = []
        by_name = {_INVENTORY.normalize_name(str(project["name"])): project for project in self._projects}
        for row in self._rows:
            project = by_name[str(row["normalized_name"])]
            packages.append(
                {
                    "name": project["name"],
                    "version": project["version"],
                    "filename": project["filename"],
                    "sha256": project["sha256"],
                    "size": project["size"],
                    "direct": True,
                    "extras": list(row["extras"]),
                    "markers": row["environment_marker"],
                    "requires": list(project.get("requires") or []),
                    "provenance": SYNTHETIC_MARKER,
                    "url": None,
                    "vcs": None,
                }
            )
        return {
            "schema_version": _VERIFY.SCHEMA_VERSION,
            "synthetic": True,
            "status": _VERIFY.SYNTHETIC_STATUS,
            "target": self.evidence["target"],
            "source": {
                "index_url": _VERIFY.SYNTHETIC_INDEX,
                "source_approved": False,
                "additional_indexes": [],
            },
            "packages": packages,
            "toolchain": {"pip_version": "UNKNOWN", "resolver": "SYNTHETIC_TEST_ONLY"},
            "claimed_state": None,
        }

    def _advance(self, expected: str, new: str) -> None:
        if self.state != expected:
            self._fail("illegal_transition")
        self.state = new

    def _fail(self, reason: str) -> NoReturn:
        self.state = "FAILED_CLOSED"
        raise WorkflowRejected(reason)

    def _invoke(self, function: Callable[..., Any], *args: Any) -> Any:
        return self._call(lambda: function(*args))

    def _call(self, function: Callable[[], Any]) -> Any:
        try:
            return function()
        except WorkflowRejected:
            raise
        except Exception as exc:
            reason = getattr(exc, "reason", None)
            if reason is None:
                raise
            self._fail(str(reason))

    def _close(self) -> None:
        if self._closed or _FS._KERNEL is None:
            self._closed = True
            return
        for handle in self._file_handles:
            _FS._KERNEL.CloseHandle(handle)
        if self._dest_handle is not None:
            self._dest_handle.close()
        if self._parent_handle is not None:
            self._parent_handle.close()
        self._closed = True


def _canonical(document: dict[str, Any]) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))
