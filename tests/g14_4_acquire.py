"""Offline acquisition policy. This module never opens a socket or runs pip."""

from __future__ import annotations

import importlib.util
import ipaddress
import os
import re
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

PREFIX = "forext-g14-4-wheelhouse-"
WHEELHOUSE_CREATED = False
NETWORK_ENABLED = False
MAX_REDIRECTS = 2
REPO = Path(__file__).resolve().parents[1]
STAGING = Path(r"C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2")
PROPOSED_INDEX_HOSTS = frozenset({"pypi.org"})
PROPOSED_ARTIFACT_HOSTS = frozenset({"files.pythonhosted.org"})
PROPOSED_INDEX_URL = "https://pypi.org/simple"
WINDOWS_BASICS = frozenset({"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"})
FORBIDDEN_ENV = frozenset(
    {
        "PIP_INDEX_URL",
        "PIP_EXTRA_INDEX_URL",
        "PIP_FIND_LINKS",
        "PIP_TRUSTED_HOST",
        "PIP_CONFIG_FILE",
        "PIP_PRE",
        "PIP_NO_BINARY",
        "PIP_ONLY_BINARY",
        "PIP_REQUIRE_VIRTUALENV",
        "PIP_CERT",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
    }
)
CREDENTIAL_MARKERS = ("PASSWORD", "SECRET", "TOKEN", "CREDENTIAL", "NETRC", "API_KEY", "PRIVATE_KEY")
BACKUP_NAMES = {
    "main example .env backup.txt",
    "# Copy to .env and fill in. docker.txt",
}
QUERY_SECRETS = {"password", "token", "secret", "access_token", "authorization", "api_key"}
REPARSE = 0x400
UNSAFE = REPARSE | 0x1000 | 0x40000 | 0x400000
FILESYSTEM_RACE_STATUS = "ACQUISITION_FILESYSTEM_BOUNDARY_UNVERIFIED"
REQUIRED_BINARY_ARGUMENT = "--only-binary=:all:"
PYTHON_TAGS = {"cp312", "py3", "py312"}
ABI_TAGS = {"none", "abi3", "cp312"}
PRE_RE = re.compile(r"(?:a|b|rc)\d|\.dev\d", re.IGNORECASE)


class DestinationRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class EnvironmentRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PolicyRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class NetworkDisabled(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AcquisitionRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _credential_key(key: str) -> bool:
    folded = key.replace("-", "_").upper()
    return any(part in folded for part in CREDENTIAL_MARKERS)


def _credential_value(value: str) -> bool:
    return "BEGIN PRIVATE KEY" in value or "Bearer " in value


def select_interpreter(interpreter: Path) -> Path:
    """Accept only an absolute python executable path. Do not search PATH."""
    if not interpreter.is_absolute() or ".." in interpreter.parts:
        raise EnvironmentRejected("untrusted_executable")
    if interpreter.name.lower() not in {"python.exe", "python"}:
        raise EnvironmentRejected("untrusted_executable")
    return interpreter


def build_acquisition_environment(
    inherited: Mapping[str, str],
    *,
    interpreter: Path,
    platform_basics: Mapping[str, str],
) -> dict[str, str]:
    """Build a child environment from an allowlist. The host mapping is not copied."""
    select_interpreter(interpreter)
    for key, value in inherited.items():
        if _credential_key(key) or _credential_value(value):
            raise EnvironmentRejected("credential_value_rejected")
        folded = key.upper()
        if folded in FORBIDDEN_ENV or folded.startswith("PIP_") or folded.endswith("_PROXY"):
            raise EnvironmentRejected("inherited_environment_rejected")
    if inherited:
        raise EnvironmentRejected("unexpected_environment")
    unknown = set(platform_basics) - WINDOWS_BASICS
    if unknown:
        raise EnvironmentRejected("unexpected_environment")
    for value in platform_basics.values():
        if _credential_value(value):
            raise EnvironmentRejected("credential_value_rejected")
    if os.name == "nt" and not {"SYSTEMROOT", "WINDIR"} <= set(platform_basics):
        raise EnvironmentRejected("missing_windows_basic")
    environment = {key: platform_basics[key] for key in sorted(platform_basics)}
    environment.update(
        {
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_CACHE_DIR": "1",
            "PIP_NO_INPUT": "1",
            "PIP_ONLY_BINARY": ":all:",
            "PYTHONNOUSERSITE": "1",
            "PYTHONSAFEPATH": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return environment


def _hosts_for(role: str) -> frozenset[str]:
    if role == "index":
        return PROPOSED_INDEX_HOSTS
    if role == "artifact":
        return PROPOSED_ARTIFACT_HOSTS
    raise PolicyRejected("unapproved_host")


def authorize_url(url: str, *, role: str) -> str:
    """Return the URL only when it matches the proposed host policy."""
    if any(token in url.lower() for token in ("%00", "%2e%2e", "%5c", "%2f%2f", "\\")):
        raise PolicyRejected("suspicious_encoding")
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise PolicyRejected("malformed_hostname") from None
    scheme = parsed.scheme.lower()
    if scheme == "http":
        raise PolicyRejected("http_url")
    if scheme == "ftp":
        raise PolicyRejected("ftp_url")
    if scheme == "file":
        raise PolicyRejected("file_url")
    if scheme.startswith(("git+", "hg+", "svn+", "bzr+")) or scheme in {"ssh", "git"}:
        raise PolicyRejected("vcs_url")
    if scheme != "https":
        raise PolicyRejected("unknown_scheme")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise PolicyRejected("url_userinfo")
    host = parsed.hostname
    if host is None or host == "":
        raise PolicyRejected("empty_hostname")
    if host.casefold() in {"localhost", "localhost."}:
        raise PolicyRejected("localhost")
    try:
        port = parsed.port
    except ValueError:
        raise PolicyRejected("unexpected_port") from None
    if port not in (None, 443):
        raise PolicyRejected("unexpected_port")
    if not host.isascii() or host.endswith(".") or "_" in host or ".." in host:
        raise PolicyRejected("malformed_hostname")
    _reject_ip(host)
    allowed = _hosts_for(role)
    if host.casefold() not in allowed:
        if role == "artifact":
            raise PolicyRejected("unexpected_artifact_host")
        raise PolicyRejected("unapproved_host")
    if ".." in Path(parsed.path).parts:
        raise PolicyRejected("suspicious_encoding")
    for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in QUERY_SECRETS:
            raise PolicyRejected("credential_query")
    if role == "index" and parsed.path.rstrip("/") != "/simple":
        raise PolicyRejected("unapproved_host")
    if role == "artifact" and not parsed.path.lower().endswith(".whl"):
        raise PolicyRejected("unexpected_artifact")
    return url


def _reject_ip(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_loopback:
        raise PolicyRejected("loopback")
    if address.is_link_local:
        raise PolicyRejected("link_local")
    if address.is_private:
        raise PolicyRejected("private_address")
    raise PolicyRejected("ip_destination")


def authorize_redirect_chain(urls: Sequence[str], *, role: str) -> str:
    if not urls:
        raise PolicyRejected("empty_redirect_chain")
    if len(urls) - 1 > MAX_REDIRECTS:
        raise PolicyRejected("excessive_redirects")
    previous_host: str | None = None
    previous_scheme: str | None = None
    current_role = role
    final = ""
    for url in urls:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        if previous_scheme == "https" and scheme == "http":
            raise PolicyRejected("https_downgrade")
        host = (parsed.hostname or "").casefold()
        if previous_host is not None and host != previous_host:
            allowed_transition = previous_host in PROPOSED_INDEX_HOSTS and host in PROPOSED_ARTIFACT_HOSTS and current_role == "index"
            if not allowed_transition:
                raise PolicyRejected("cross_host_redirect")
            current_role = "artifact"
        final = authorize_url(url, role=current_role)
        previous_host = host
        previous_scheme = scheme
    if role == "artifact" and (previous_host not in PROPOSED_ARTIFACT_HOSTS):
        raise PolicyRejected("unexpected_artifact_host")
    return final


def reject_additional_indexes(indexes: Sequence[str]) -> None:
    if indexes:
        raise PolicyRejected("unapproved_additional_index")


def _tag_problem(filename: str) -> str | None:
    if not filename.endswith(".whl"):
        return "unexpected_artifact"
    parts = filename[: -len(".whl")].split("-")
    if len(parts) < 5:
        return "unsupported_wheel_tag"
    platform = parts[-1].lower()
    abi = parts[-2]
    python = parts[-3]
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


def assess_wheel_candidate(candidate: Mapping[str, Any], *, binary_policy: str = "only-binary") -> None:
    """Reject a candidate that is not a final pure or named wheel. Does not download it."""
    if binary_policy != "only-binary":
        raise AcquisitionRejected("prefer_binary_not_sufficient")
    if candidate.get("partial") is True or candidate.get("complete") is False:
        raise AcquisitionRejected("partial_download")
    if candidate.get("yanked") is True:
        raise AcquisitionRejected("yanked_release")
    filename = str(candidate.get("filename", ""))
    lowered = filename.lower()
    if lowered.endswith((".tar.gz", ".tar.bz2", ".zip")) or candidate.get("kind") == "sdist":
        raise AcquisitionRejected("source_distribution")
    if not lowered.endswith(".whl"):
        raise AcquisitionRejected("unexpected_artifact")
    problem = _tag_problem(filename)
    if problem is not None:
        raise AcquisitionRejected(problem)
    if not filename.lower().endswith("-any.whl"):
        raise AcquisitionRejected("native_platform_unverified")
    version = str(candidate.get("version", ""))
    if _is_prerelease(version):
        raise AcquisitionRejected("unapproved_prerelease")
    redirects = candidate.get("redirects") or [str(candidate.get("url", ""))]
    if not isinstance(redirects, list) or not redirects:
        raise AcquisitionRejected("missing_artifact_url")
    authorize_redirect_chain([str(item) for item in redirects], role="artifact")


def _is_prerelease(version: str) -> bool:
    return PRE_RE.search(version) is not None


def _logical_path(dest: Path) -> Path:
    if ".." in dest.parts:
        raise DestinationRejected("path_traversal")
    absolute = dest if dest.is_absolute() else Path.cwd() / dest
    return Path(os.path.normpath(str(absolute)))


def _link_info(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _reject_stat(info: os.stat_result, reason: str) -> None:
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & UNSAFE:
        raise DestinationRejected(reason)
    if not stat.S_ISDIR(info.st_mode) and getattr(info, "st_nlink", 1) > 1:
        raise DestinationRejected("hard_link")


def reject_case_colliding_names(names: Sequence[str]) -> None:
    folded: dict[str, str] = {}
    for name in names:
        key = name.casefold()
        if key in folded and folded[key] != name:
            raise DestinationRejected("case_collision")
        folded[key] = name


def reject_member_name(name: str) -> None:
    if name in BACKUP_NAMES:
        raise DestinationRejected("sensitive_backup_filename")
    if name == "live_safety_state.json":
        raise DestinationRejected("operational_state_filename")
    if name != Path(name).name or name in {"", ".", ".."}:
        raise DestinationRejected("path_traversal")


def assert_destination_boundary(dest: Path) -> Path:
    logical = _logical_path(dest)
    if logical == REPO or REPO in logical.parents:
        raise DestinationRejected("inside_repository")
    if any(part.casefold() == "onedrive" for part in logical.parts):
        raise DestinationRejected("inside_onedrive")
    if any(part.casefold() == "concensus-forecast" for part in logical.parts):
        raise DestinationRejected("inside_consensus_forecast")
    text = str(logical).casefold()
    if "docker\\volumes" in text or "docker/volumes" in text or "wsl$" in text or "docker_data.vhdx" in text:
        raise DestinationRejected("inside_docker_volume")
    if logical == STAGING or STAGING in logical.parents:
        raise DestinationRejected("inside_staging_context")
    blocked = {"shadow_state", "shadow-state", "operational_state", "live_safety_state.json"}
    if any(part.casefold() in blocked for part in logical.parts):
        raise DestinationRejected("operational_state_path")
    info = _link_info(dest)
    if info is not None:
        _reject_stat(info, "symlink_or_reparse")
        if not stat.S_ISDIR(info.st_mode):
            raise DestinationRejected("destination_not_directory")
    for parent in logical.parents:
        if parent == parent.parent:
            break
        parent_info = _link_info(parent)
        if parent_info is not None:
            _reject_stat(parent_info, "symlink_parent")
    return logical


def _child_names(dest: Path) -> list[str]:
    return [child.name for child in dest.iterdir()]


def assert_destination_allowed(dest: Path) -> None:
    assert_destination_boundary(dest)
    if dest.exists() and any(True for _ in dest.iterdir()):
        names = _child_names(dest)
        reject_case_colliding_names(names)
        for name in names:
            reject_member_name(name)
        raise DestinationRejected("destination_not_empty")
    if WHEELHOUSE_CREATED:
        raise DestinationRejected("wheelhouse_must_not_exist_in_gate_a")


def create_exclusive_file(directory: Path, name: str, data: bytes) -> None:
    """Create one new file. An existing path is not replaced and a short write is not success."""
    assert_destination_boundary(directory)
    reject_member_name(name)
    reject_case_colliding_names([*(_child_names(directory) if directory.exists() else []), name])
    target = directory / name
    if target.parent != directory or _link_info(target) is not None:
        raise DestinationRejected("unsafe_file_replacement")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(target, flags)
    try:
        written = os.write(descriptor, data)
        if written != len(data):
            raise DestinationRejected("interrupted_write")
    except DestinationRejected:
        raise
    except OSError:
        raise DestinationRejected("interrupted_write") from None
    finally:
        os.close(descriptor)


def _inventory() -> Any:
    path = Path(__file__).with_name("g14_4_inventory.py")
    spec = importlib.util.spec_from_file_location("g14_4_inventory_for_acquire", path)
    if spec is None or spec.loader is None:
        raise AcquisitionRejected("inventory_helper_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_acquisition(
    *,
    inherited: Mapping[str, str],
    interpreter: Path,
    platform_basics: Mapping[str, str],
    destination: Path,
    requirements_text: str,
    candidates: Sequence[Mapping[str, Any]],
    extra_indexes: Sequence[str] = (),
    find_links: Sequence[str] = (),
    binary_policy: str = "only-binary",
) -> dict[str, Any]:
    """Check policy for a future download. This function performs no network I/O."""
    if binary_policy != "only-binary":
        raise AcquisitionRejected("prefer_binary_not_sufficient")
    reject_additional_indexes(extra_indexes)
    if find_links:
        raise AcquisitionRejected("unapproved_find_links")
    environment = build_acquisition_environment(
        inherited,
        interpreter=interpreter,
        platform_basics=platform_basics,
    )
    assert_destination_allowed(destination)
    rows = _inventory().parse_requirement_document(requirements_text)
    expected = {str(row["normalized_name"]): row for row in rows}
    seen: dict[str, str] = {}
    authorized: list[tuple[str, str]] = []
    authorize_url(PROPOSED_INDEX_URL, role="index")
    authorized.append((PROPOSED_INDEX_URL, "index"))
    for candidate in candidates:
        name = re.sub(r"[-_.]+", "-", str(candidate.get("name", ""))).lower()
        if name not in expected:
            raise AcquisitionRejected("unexpected_package")
        version = str(candidate.get("version", ""))
        if name in seen and seen[name] != version:
            raise AcquisitionRejected("conflicting_versions")
        seen[name] = version
        assess_wheel_candidate(candidate, binary_policy=binary_policy)
        redirects = candidate.get("redirects") or [str(candidate.get("url", ""))]
        authorize_redirect_chain([str(item) for item in redirects], role="artifact")
        authorized.append((str(redirects[-1]), "artifact"))
    missing = set(expected) - set(seen)
    if missing:
        raise AcquisitionRejected("missing_wheel")
    return {
        "environment": environment,
        "authorized": authorized,
        "wheel_only": True,
        "required_binary_argument": REQUIRED_BINARY_ARGUMENT,
        "network_calls": 0,
        "executed": False,
        "filesystem_race_status": FILESYSTEM_RACE_STATUS,
    }


class OfflineAcquisitionTransport:
    """Policy gate with no network sender. Gate B has not supplied one."""

    def commit(self, plan: Mapping[str, Any]) -> None:
        for url, role in plan["authorized"]:
            authorize_url(str(url), role=str(role))
        if NETWORK_ENABLED:
            raise NetworkDisabled("network_not_authorised")
        raise NetworkDisabled("network_not_authorised")


def commit_acquisition(plan: Mapping[str, Any]) -> None:
    OfflineAcquisitionTransport().commit(plan)
