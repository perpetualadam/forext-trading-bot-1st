"""Wheelhouse checks. Hashes, archives, metadata, and the selected graph are separate."""

from __future__ import annotations

import base64
import email.parser
import hashlib
import importlib.util
import io
import os
import re
import stat
import zipfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "g14_4_lock_schema_v1"
SYNTHETIC_STATUS = "SYNTHETIC_NOT_AN_APPROVED_LOCK"
SYNTHETIC_INDEX = "synthetic://fixture"
COMPLETION_STATES = {
    "RESOLUTION_COMPLETE",
    "ARTIFACT_ACQUISITION_COMPLETE",
    "INDEPENDENT_ARTIFACT_VERIFICATION_COMPLETE",
}
BACKUP_NAMES = {
    "main example .env backup.txt",
    "# Copy to .env and fill in. docker.txt",
}
CREDENTIAL_KEYS = {
    "password",
    "token",
    "secret",
    "authorization",
    "api_key",
    "access_token",
}
TOP_KEYS = {
    "schema_version",
    "synthetic",
    "status",
    "target",
    "source",
    "packages",
    "toolchain",
    "claimed_state",
}
PACKAGE_KEYS = {
    "name",
    "version",
    "filename",
    "sha256",
    "size",
    "direct",
    "extras",
    "markers",
    "requires",
    "provenance",
    "url",
    "vcs",
}
PYTHON_TAGS = {"cp312", "py3", "py312"}
ABI_TAGS = {"none", "abi3", "cp312"}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
REPARSE = 0x400
UNSAFE = REPARSE | 0x1000 | 0x40000 | 0x400000
ALLOWED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
DIST_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?:\s*\[(?P<extras>[^\]]*)\])?"
    r"(?:\s*\((?P<paren>[^)]*)\))?"
    r"(?P<bare>(?:\s*(?:==|!=|<=|>=|~=|<|>)[^;]*)?)"
    r"(?:\s*;\s*(?P<marker>.+))?$"
)
PRE_RE = re.compile(r"(?:a|b|rc)\d+|\.dev\d+", re.IGNORECASE)


class VerificationRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class WheelLimits:
    def __init__(
        self,
        max_members: int = 20000,
        max_member_uncompressed: int = 32 * 1024 * 1024,
        max_total_uncompressed: int = 256 * 1024 * 1024,
        max_ratio: int = 100,
        max_metadata_bytes: int = 1_000_000,
    ) -> None:
        self.max_members = max_members
        self.max_member_uncompressed = max_member_uncompressed
        self.max_total_uncompressed = max_total_uncompressed
        self.max_ratio = max_ratio
        self.max_metadata_bytes = max_metadata_bytes


class RequiresDist:
    def __init__(self, name: str, specifier: str, marker: str | None) -> None:
        self.name = name
        self.specifier = specifier
        self.marker = marker


class InspectedWheel:
    def __init__(
        self,
        name: str,
        version: str,
        requires_python: str | None,
        requires_python_status: str,
        provides_extra: frozenset[str],
        requires_dist: tuple[RequiresDist, ...],
        pure: bool,
    ) -> None:
        self.name = name
        self.version = version
        self.requires_python = requires_python
        self.requires_python_status = requires_python_status
        self.provides_extra = provides_extra
        self.requires_dist = requires_dist
        self.pure = pure


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _archive_stem(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name)


def parse_wheel_filename(filename: str) -> dict[str, str] | None:
    if not filename.endswith(".whl"):
        return None
    parts = filename[: -len(".whl")].split("-")
    if len(parts) < 5:
        return None
    platform, abi, python = parts[-1], parts[-2], parts[-3]
    version = parts[-4]
    name = "-".join(parts[:-4])
    if not name or not version:
        return None
    return {"name": name, "version": version, "python": python, "abi": abi, "platform": platform}


def _tag_problem(parsed: dict[str, str]) -> str | None:
    python = parsed["python"]
    abi = parsed["abi"]
    platform = parsed["platform"].lower()
    if python not in PYTHON_TAGS:
        if python.startswith(("cp2", "cp3", "py2", "py3")):
            return "incorrect_python"
        return "unsupported_wheel_tag"
    if any(token in platform for token in ("win", "macos", "aarch64", "arm", "i686")):
        return "incorrect_architecture"
    platform_ok = platform == "any" or (
        platform.endswith("x86_64") and platform.startswith(("manylinux", "musllinux", "linux"))
    )
    if abi not in ABI_TAGS or not platform_ok:
        return "unsupported_wheel_tag"
    return None


def _filename_problem(filename: str) -> str | None:
    name = Path(filename).name
    if name in BACKUP_NAMES or filename in BACKUP_NAMES:
        return "sensitive_backup_filename"
    if name == "live_safety_state.json":
        return "operational_state_filename"
    if filename.startswith(("/", "\\")) or (len(filename) > 2 and filename[1] == ":"):
        return "absolute_path"
    if ".." in Path(filename).parts or filename.startswith(".."):
        return "path_traversal"
    lowered = filename.lower()
    if lowered.endswith((".tar.gz", ".tar.bz2", ".zip")):
        return "source_distribution"
    parsed = parse_wheel_filename(filename)
    if parsed is None:
        return "unsupported_wheel_tag"
    return _tag_problem(parsed)


def _reject_credentials(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in CREDENTIAL_KEYS:
                raise VerificationRejected("credential_metadata")
            _reject_credentials(item)
    elif isinstance(value, list):
        for item in value:
            _reject_credentials(item)
    elif isinstance(value, str) and ("Bearer " in value or "BEGIN PRIVATE KEY" in value):
        raise VerificationRejected("credential_metadata")


def _require_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    missing = allowed - set(value)
    if missing:
        raise VerificationRejected("incomplete_manifest")
    for key in value:
        if str(key).lower() in CREDENTIAL_KEYS:
            raise VerificationRejected("credential_metadata")
        if key not in allowed:
            raise VerificationRejected(f"unknown_field:{label}")


def _member_problem(name: str) -> str | None:
    if name.startswith(("/", "\\")) or (len(name) > 2 and name[1] == ":"):
        return "absolute_archive_path"
    if "\\" in name or ".." in Path(name).parts or name.startswith(".."):
        return "archive_path_traversal"
    return None


def _read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limits: WheelLimits) -> bytes:
    if info.flag_bits & 0x1 or info.flag_bits & 0x40:
        raise VerificationRejected("encrypted_entry")
    if info.compress_type not in ALLOWED_COMPRESSION:
        raise VerificationRejected("unsupported_compression")
    if info.file_size > limits.max_member_uncompressed:
        raise VerificationRejected("excessive_uncompressed_size")
    if info.compress_size <= 0 and info.file_size > 0:
        raise VerificationRejected("excessive_compression_ratio")
    if info.compress_size > 0 and info.file_size / info.compress_size > limits.max_ratio:
        raise VerificationRejected("excessive_compression_ratio")
    chunks: list[bytes] = []
    total = 0
    with archive.open(info) as handle:
        while True:
            block = handle.read(65536)
            if not block:
                break
            total += len(block)
            if total > limits.max_member_uncompressed:
                raise VerificationRejected("excessive_uncompressed_size")
            chunks.append(block)
    return b"".join(chunks)


def _version_tuple(text: str) -> tuple[int, ...]:
    match = re.match(r"^(\d+(?:\.\d+)*)", text)
    if match is None:
        raise VerificationRejected("malformed_metadata")
    return tuple(int(part) for part in match.group(1).split("."))


def _specifier_needs_patch(spec: str) -> bool:
    for clause in spec.split(","):
        numbers = re.findall(r"\d+(?:\.\d+)*", clause)
        if any(number.count(".") >= 2 for number in numbers):
            return True
    return False


def _compare_versions(left: tuple[int, ...], operator: str, right: tuple[int, ...]) -> bool:
    width = max(len(left), len(right))
    padded_left = left + (0,) * (width - len(left))
    padded_right = right + (0,) * (width - len(right))
    if operator == "==":
        return padded_left == padded_right
    if operator == "!=":
        return padded_left != padded_right
    if operator == ">=":
        return padded_left >= padded_right
    if operator == "<=":
        return padded_left <= padded_right
    if operator == ">":
        return padded_left > padded_right
    if operator == "<":
        return padded_left < padded_right
    if operator == "~=":
        prefix = len(right) - 1
        return padded_left[:prefix] == padded_right[:prefix] and padded_left >= padded_right
    raise VerificationRejected("malformed_metadata")


def version_satisfies(version: str, specifier: str) -> bool:
    if specifier.strip() == "":
        return True
    left = _version_tuple(version)
    for clause in specifier.split(","):
        text = clause.strip()
        match = re.match(r"^(==|!=|<=|>=|~=|<|>)\s*([A-Za-z0-9.*+!_-]+)$", text)
        if match is None:
            raise VerificationRejected("malformed_metadata")
        right = _version_tuple(match.group(2))
        if not _compare_versions(left, match.group(1), right):
            return False
    return True


def requires_python_status(specifier: str | None) -> str:
    if specifier is None or specifier.strip() == "":
        return "compatible"
    if _specifier_needs_patch(specifier):
        return "unknown"
    target = (3, 12)
    try:
        ok = version_satisfies("3.12", specifier)
    except VerificationRejected:
        return "unknown"
    if not ok:
        return "incompatible"
    if target != (3, 12):
        return "unknown"
    return "compatible"


def _parse_requires_dist(value: str) -> RequiresDist:
    match = DIST_RE.match(value.strip())
    if match is None:
        raise VerificationRejected("malformed_metadata")
    specifier = (match.group("paren") or match.group("bare") or "").strip()
    marker = match.group("marker")
    if marker is not None:
        marker = marker.strip()
    return RequiresDist(name=match.group("name"), specifier=specifier, marker=marker)


def _load_inventory() -> Any:
    path = Path(__file__).with_name("g14_4_inventory.py")
    spec = importlib.util.spec_from_file_location("g14_4_inventory_for_verify", path)
    if spec is None or spec.loader is None:
        raise VerificationRejected("inventory_helper_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _marker_result(marker: str | None, extra: str) -> bool | None:
    if marker is None:
        return True
    module = _load_inventory()
    for name in ("sys_platform", "python_version", "platform_machine"):
        if name not in module.TARGET_ENVIRONMENT:
            raise VerificationRejected("marker_unverified")
    try:
        outcome = module.evaluate_marker(marker, extra=extra)
    except module.InventoryMismatch:
        raise VerificationRejected("malformed_marker") from None
    if outcome is None:
        return None
    if not isinstance(outcome, bool):
        raise VerificationRejected("malformed_marker")
    return outcome


def inspect_wheel_bytes(
    data: bytes,
    *,
    filename: str,
    declared_name: str,
    declared_version: str,
    limits: WheelLimits | None = None,
) -> InspectedWheel:
    """Inspect a wheel in memory. Members are not extracted or imported."""
    bounds = limits or WheelLimits()
    parsed = parse_wheel_filename(Path(filename).name)
    if parsed is None or _tag_problem(parsed) is not None:
        raise VerificationRejected("unsupported_wheel_tag")
    if PRE_RE.search(parsed["version"]):
        raise VerificationRejected("unapproved_prerelease")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise VerificationRejected("malformed_zip") from None
    with archive:
        infos = archive.infolist()
        if len(infos) > bounds.max_members:
            raise VerificationRejected("excessive_member_count")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise VerificationRejected("duplicate_archive_member")
        folded: dict[str, str] = {}
        for name in names:
            problem = _member_problem(name)
            if problem is not None:
                raise VerificationRejected(problem)
            key = name.casefold()
            if key in folded and folded[key] != name:
                raise VerificationRejected("case_colliding_member")
            folded[key] = name
        total = 0
        payloads: dict[str, bytes] = {}
        for info in infos:
            if info.file_size > bounds.max_member_uncompressed:
                raise VerificationRejected("excessive_uncompressed_size")
            total += info.file_size
            if total > bounds.max_total_uncompressed:
                raise VerificationRejected("excessive_uncompressed_size")
            payloads[info.filename] = _read_member(archive, info, bounds)
    prefix = f"{_archive_stem(parsed['name'])}-{parsed['version']}.dist-info/"
    wheel_name = prefix + "WHEEL"
    metadata_name = prefix + "METADATA"
    record_name = prefix + "RECORD"
    if wheel_name not in payloads:
        raise VerificationRejected("missing_wheel_metadata")
    if metadata_name not in payloads:
        raise VerificationRejected("missing_metadata")
    if record_name not in payloads:
        raise VerificationRejected("missing_record")
    for label, member in ((wheel_name, payloads[wheel_name]), (metadata_name, payloads[metadata_name])):
        if len(member) > bounds.max_metadata_bytes:
            raise VerificationRejected("excessive_uncompressed_size")
        if b"\x00" in member:
            raise VerificationRejected("malformed_metadata" if label.endswith("METADATA") else "malformed_wheel_metadata")
    _check_record(record_name, payloads)
    tags = _wheel_tags(payloads[wheel_name].decode("utf-8"))
    expected_tag = f"{parsed['python']}-{parsed['abi']}-{parsed['platform']}"
    if expected_tag not in tags:
        raise VerificationRejected("incompatible_wheel_tag")
    message = _metadata_message(payloads[metadata_name].decode("utf-8"))
    meta_name = message.get("Name")
    meta_version = message.get("Version")
    if not meta_name or not meta_version:
        raise VerificationRejected("malformed_metadata")
    if normalize_name(meta_name) != normalize_name(declared_name) or normalize_name(meta_name) != normalize_name(parsed["name"]):
        raise VerificationRejected("conflicting_package_name")
    if meta_version != declared_version or meta_version != parsed["version"]:
        raise VerificationRejected("conflicting_package_version")
    if message.get("Yanked"):
        raise VerificationRejected("yanked_release")
    python_status = requires_python_status(message.get("Requires-Python"))
    if python_status == "incompatible":
        raise VerificationRejected("incompatible_python")
    if python_status == "unknown":
        raise VerificationRejected("python_requirement_unverified")
    requires = tuple(_parse_requires_dist(item) for item in message.get_all("Requires-Dist") or [])
    extras = frozenset(message.get_all("Provides-Extra") or [])
    pure = parsed["platform"] == "any"
    if not pure:
        raise VerificationRejected("native_platform_unverified")
    return InspectedWheel(
        name=normalize_name(meta_name),
        version=meta_version,
        requires_python=message.get("Requires-Python"),
        requires_python_status=python_status,
        provides_extra=extras,
        requires_dist=requires,
        pure=pure,
    )


def _metadata_message(text: str) -> email.message.Message:
    if "\n\n" in text.replace("\r\n", "\n"):
        raise VerificationRejected("malformed_metadata")
    if not text.startswith("Metadata-Version:"):
        raise VerificationRejected("malformed_metadata")
    return email.parser.Parser().parsestr(text)


def _wheel_tags(text: str) -> set[str]:
    tags: set[str] = set()
    for line in text.splitlines():
        if line.startswith("Tag:"):
            tags.add(line.split(":", 1)[1].strip())
    if not tags:
        raise VerificationRejected("malformed_wheel_metadata")
    return tags


def _record_digest(data: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii")
    return "sha256=" + encoded.rstrip("=")


def _check_record(record_name: str, payloads: dict[str, bytes]) -> None:
    try:
        text = payloads[record_name].decode("utf-8")
    except UnicodeError:
        raise VerificationRejected("malformed_record") from None
    listed: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        if line == "":
            continue
        parts = line.split(",")
        if len(parts) != 3:
            raise VerificationRejected("malformed_record")
        path, digest, size = parts
        if path in listed:
            raise VerificationRejected("duplicate_archive_member")
        listed[path] = (digest, size)
    if record_name not in listed:
        raise VerificationRejected("record_missing_member")
    record_digest, record_size = listed[record_name]
    if record_digest or record_size:
        raise VerificationRejected("malformed_record")
    for path, payload in payloads.items():
        if path not in listed:
            raise VerificationRejected("record_missing_member")
        if path == record_name:
            continue
        digest, size = listed[path]
        if digest != _record_digest(payload):
            raise VerificationRejected("record_hash_mismatch")
        if size != str(len(payload)):
            raise VerificationRejected("record_size_mismatch")
    for path in listed:
        if path not in payloads:
            raise VerificationRejected("record_missing_member")


def _applicable(info: InspectedWheel, requested: set[str]) -> list[RequiresDist]:
    contexts = ["", *sorted(requested)]
    selected: list[RequiresDist] = []
    seen: set[tuple[str, str]] = set()
    for requirement in info.requires_dist:
        outcomes = [_marker_result(requirement.marker, extra) for extra in contexts]
        if any(outcome is None for outcome in outcomes):
            raise VerificationRejected("marker_unverified")
        if any(outcome is True for outcome in outcomes):
            key = (normalize_name(requirement.name), requirement.specifier)
            if key not in seen:
                seen.add(key)
                selected.append(requirement)
    return selected


def assert_dependency_graph(packages: list[dict[str, Any]], inspected: dict[str, InspectedWheel]) -> None:
    selected = {normalize_name(str(package["name"])): str(package["version"]) for package in packages}
    if len(selected) != len(packages):
        raise VerificationRejected("duplicate_package")
    for package in packages:
        key = normalize_name(str(package["name"]))
        info = inspected[key]
        requested = {str(extra) for extra in package["extras"]}
        missing_extra = requested - set(info.provides_extra)
        if missing_extra:
            raise VerificationRejected("missing_requested_extra")
        for requirement in _applicable(info, requested):
            name = normalize_name(requirement.name)
            if name not in selected:
                raise VerificationRejected("missing_dependency")
            if not version_satisfies(selected[name], requirement.specifier):
                raise VerificationRejected("unsatisfied_constraint")


def verify_member_bytes(
    manifest: dict[str, Any],
    members: dict[str, bytes],
    *,
    limits: WheelLimits | None = None,
) -> dict[str, str]:
    """Verify bytes already read from a held destination handle."""
    return verify_wheelhouse(manifest, Path("."), members=members, limits=limits)


def verify_wheelhouse(
    manifest: dict[str, Any],
    wheelhouse: Path,
    *,
    limits: WheelLimits | None = None,
    members: dict[str, bytes] | None = None,
) -> dict[str, str]:
    """Accept a wheelhouse only after hash, archive, metadata, and graph checks."""
    if not isinstance(manifest, dict):
        raise VerificationRejected("incomplete_manifest")
    _reject_credentials(manifest)
    _require_keys(manifest, TOP_KEYS, "manifest")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise VerificationRejected("malformed_schema_version")
    if manifest["synthetic"] is not True or manifest["status"] != SYNTHETIC_STATUS:
        raise VerificationRejected("false_completion_claim")
    if manifest["claimed_state"] in COMPLETION_STATES:
        raise VerificationRejected("false_completion_claim")
    source = manifest["source"]
    if not isinstance(source, dict):
        raise VerificationRejected("incomplete_manifest")
    if source.get("additional_indexes"):
        raise VerificationRejected("unapproved_additional_index")
    if source.get("index_url") != SYNTHETIC_INDEX or source.get("source_approved") is not False:
        raise VerificationRejected("unknown_source")
    packages = manifest["packages"]
    if not isinstance(packages, list):
        raise VerificationRejected("incomplete_manifest")
    seen_names: dict[str, str] = {}
    seen_files: set[str] = set()
    folded: dict[str, str] = {}
    expected: dict[str, dict[str, Any]] = {}
    for package in packages:
        if not isinstance(package, dict):
            raise VerificationRejected("incomplete_manifest")
        _require_keys(package, PACKAGE_KEYS, "package")
        if not package.get("provenance"):
            raise VerificationRejected("missing_provenance")
        if package.get("url"):
            raise VerificationRejected("unapproved_direct_url")
        if package.get("vcs"):
            raise VerificationRejected("unapproved_vcs")
        filename = str(package["filename"])
        problem = _filename_problem(filename)
        if problem is not None:
            raise VerificationRejected(problem)
        digest = str(package["sha256"])
        if not HASH_RE.fullmatch(digest):
            raise VerificationRejected("malformed_sha256")
        if filename in seen_files:
            raise VerificationRejected("duplicate_filename")
        fold = filename.casefold()
        if fold in folded:
            raise VerificationRejected("case_collision")
        seen_files.add(filename)
        folded[fold] = filename
        key = normalize_name(str(package["name"]))
        if key in seen_names:
            if seen_names[key] != package["version"]:
                raise VerificationRejected("conflicting_versions")
            raise VerificationRejected("duplicate_package")
        seen_names[key] = str(package["version"])
        expected[filename] = package
    for package in packages:
        for requirement in package["requires"]:
            if normalize_name(str(requirement)) not in seen_names:
                raise VerificationRejected("missing_dependency")
    if members is None:
        if not wheelhouse.is_dir():
            raise VerificationRejected("missing_wheel")
        members = {}
        for path in wheelhouse.rglob("*"):
            info = os.lstat(path)
            rel = path.relative_to(wheelhouse).as_posix()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & UNSAFE:
                raise VerificationRejected("symlink_or_reparse")
            if stat.S_ISDIR(info.st_mode):
                continue
            disk_problem = _filename_problem(rel)
            if disk_problem in {"sensitive_backup_filename", "operational_state_filename", "source_distribution"}:
                raise VerificationRejected(disk_problem)
            members[rel] = path.read_bytes()
    found: set[str] = set()
    inspected: dict[str, InspectedWheel] = {}
    for rel, data in members.items():
        if rel not in expected:
            if rel.endswith(".whl"):
                raise VerificationRejected("extra_wheel")
            raise VerificationRejected("extra_non_wheel")
        package = expected[rel]
        if hashlib.sha256(data).hexdigest() != package["sha256"]:
            raise VerificationRejected("hash_mismatch")
        if len(data) != package["size"]:
            raise VerificationRejected("size_mismatch")
        inspected[normalize_name(str(package["name"]))] = inspect_wheel_bytes(
            data,
            filename=rel,
            declared_name=str(package["name"]),
            declared_version=str(package["version"]),
            limits=limits,
        )
        found.add(rel)
    if found != set(expected):
        raise VerificationRejected("missing_wheel")
    assert_dependency_graph(packages, inspected)
    return {
        "hash_integrity": "PASS",
        "archive_structure": "PASS",
        "wheel_metadata": "PASS",
        "dependency_graph": "CONSISTENT_FOR_SYNTHETIC_SET",
        "production_dependency_graph": "DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED",
        "source_provenance": "SYNTHETIC_NOT_AN_APPROVED_SOURCE",
        "real_wheelhouse_acquired": "false",
        "real_dependency_lock_created": "false",
    }


def accept_verified_lock(manifest: dict[str, Any], wheelhouse: Path) -> None:
    """A synthetic or provenance-free set cannot become a production lock."""
    verify_wheelhouse(manifest, wheelhouse)
    raise VerificationRejected("provenance_unverified")


def _record_hash(data: bytes) -> str:
    return _record_digest(data)


def build_synthetic_wheel(
    name: str,
    version: str,
    *,
    python_tag: str = "py3",
    abi_tag: str = "none",
    platform_tag: str = "any",
    requires_python: str | None = ">=3.12",
    requires_dist: list[str] | None = None,
    provides_extra: list[str] | None = None,
    metadata_name: str | None = None,
    metadata_version: str | None = None,
    yanked: bool = False,
    omit: frozenset[str] = frozenset(),
    metadata_text: str | None = None,
    record_text: str | None = None,
    record_digest_for: dict[str, str] | None = None,
    record_size_for: dict[str, str] | None = None,
    omit_from_record: frozenset[str] = frozenset(),
    extra_record_paths: tuple[str, ...] = (),
) -> bytes:
    """Build a tiny in-memory wheel. It is synthetic and must not be installed."""
    prefix = f"{_archive_stem(name)}-{version}.dist-info/"
    wheel_text = "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: g14-6-synthetic",
            "Root-Is-Purelib: true",
            f"Tag: {python_tag}-{abi_tag}-{platform_tag}",
            "",
        ]
    )
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {metadata_name or name}",
        f"Version: {metadata_version or version}",
        "Summary: synthetic-fixture",
    ]
    if requires_python:
        lines.append(f"Requires-Python: {requires_python}")
    if yanked:
        lines.append("Yanked: synthetic")
    for extra in provides_extra or []:
        lines.append(f"Provides-Extra: {extra}")
    for requirement in requires_dist or []:
        lines.append(f"Requires-Dist: {requirement}")
    lines.append("")
    members = {
        prefix + "WHEEL": wheel_text.encode("utf-8"),
        prefix + "METADATA": (metadata_text or "\n".join(lines)).encode("utf-8"),
    }
    for label in omit:
        members.pop(prefix + label, None)
    record_lines: list[str] = []
    if record_text is None:
        for path, payload in members.items():
            if path in omit_from_record:
                continue
            digest = (record_digest_for or {}).get(path, _record_hash(payload))
            size = (record_size_for or {}).get(path, str(len(payload)))
            record_lines.append(f"{path},{digest},{size}")
        record_lines.append(f"{prefix}RECORD,,")
        for path in extra_record_paths:
            record_lines.append(f"{path},sha256=abcd,1")
        if "RECORD" not in omit:
            members[prefix + "RECORD"] = ("\n".join(record_lines) + "\n").encode("utf-8")
    elif "RECORD" not in omit:
        members[prefix + "RECORD"] = record_text.encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, payload in members.items():
            archive.writestr(path, payload)
    return buffer.getvalue()
