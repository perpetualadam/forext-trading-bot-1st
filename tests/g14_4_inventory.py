"""Requirement parsing for the offline acquisition tools.

Direct URL and VCS forms are rejected. Environment markers are kept.
This module does not download, install, or evaluate host platform markers.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

NATIVE = frozenset({"numpy", "pandas", "psycopg2-binary"})
NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
SPEC_RE = re.compile(
    r"^(?:==|!=|<=|>=|~=|<|>)\s*[A-Za-z0-9.*+!_-]+"
    r"(?:\s*,\s*(?:==|!=|<=|>=|~=|<|>)\s*[A-Za-z0-9.*+!_-]+)*$"
)
TOKEN_RE = re.compile(
    r"\s+|<=|>=|===|==|~=|!=|<|>|\(|\)|\b(?:and|or|not)\b|'[^']*'|\"[^\"]*\"|[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)*|."
)
TARGET_ENVIRONMENT: dict[str, str | None] = {
    "os_name": "posix",
    "sys_platform": "linux",
    "platform_system": "Linux",
    "platform_machine": "x86_64",
    "platform_python_implementation": "CPython",
    "python_version": "3.12",
    "implementation_name": "cpython",
    "python_full_version": None,
    "implementation_version": None,
    "platform_release": None,
    "platform_version": None,
}
_UNKNOWN = object()


class InventoryMismatch(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _tokens(marker: str) -> list[str]:
    tokens = [token for token in TOKEN_RE.findall(marker) if not token.isspace()]
    if "".join(tokens) != marker.replace(" ", "").replace("\t", ""):
        raise InventoryMismatch("malformed_marker")
    allowed = {"(", ")", "==", "!=", "<=", ">=", "~=", "<", ">", "and", "or", "not"}
    if any(token not in allowed and not _atom(token) for token in tokens):
        raise InventoryMismatch("malformed_marker")
    return tokens


def _atom(token: str) -> bool:
    if token.startswith(("'", '"')) and token.endswith(("'", '"')) and len(token) >= 2:
        return "\\" not in token
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)*", token))


def validate_marker(marker: str) -> None:
    """Reject a marker that is not a supported boolean expression."""
    if marker.strip() == "":
        raise InventoryMismatch("malformed_marker")
    tokens = _tokens(marker.strip())
    _parse_or(tokens)


def _parse_or(tokens: list[str]) -> None:
    _parse_and(tokens)
    while tokens and tokens[0] == "or":
        tokens.pop(0)
        _parse_and(tokens)
    if tokens:
        raise InventoryMismatch("malformed_marker")


def _parse_and(tokens: list[str]) -> None:
    _parse_not(tokens)
    while tokens and tokens[0] == "and":
        tokens.pop(0)
        _parse_not(tokens)


def _parse_not(tokens: list[str]) -> None:
    if not tokens:
        raise InventoryMismatch("malformed_marker")
    if tokens[0] == "not":
        tokens.pop(0)
        _parse_not(tokens)
        return
    if tokens[0] == "(":
        tokens.pop(0)
        saved = list(tokens)
        try:
            _parse_or_inner(tokens)
        except InventoryMismatch:
            tokens[:] = saved
            raise
        if not tokens or tokens.pop(0) != ")":
            raise InventoryMismatch("malformed_marker")
        return
    _parse_comparison(tokens)


def _parse_or_inner(tokens: list[str]) -> None:
    _parse_and(tokens)
    while tokens and tokens[0] == "or":
        tokens.pop(0)
        _parse_and(tokens)


def _parse_comparison(tokens: list[str]) -> None:
    if len(tokens) < 3 or not _atom(tokens[0]):
        raise InventoryMismatch("malformed_marker")
    operator = tokens[1]
    if operator not in {"==", "!=", "<=", ">=", "~=", "<", ">"}:
        raise InventoryMismatch("malformed_marker")
    if not _atom(tokens[2]):
        raise InventoryMismatch("malformed_marker")
    del tokens[:3]


def _version_key(value: str) -> tuple[int, ...] | None:
    if re.fullmatch(r"\d+(?:\.\d+)*", value) is None:
        return None
    return tuple(int(part) for part in value.split("."))


def _compare(left: object, operator: str, right: object) -> bool | None:
    if left is _UNKNOWN or right is _UNKNOWN:
        return None
    if not isinstance(left, str) or not isinstance(right, str):
        return None
    if operator in {"==", "!="}:
        left_key = _version_key(left)
        right_key = _version_key(right)
        if left_key is not None and right_key is not None:
            equal = left_key == right_key
        else:
            equal = left == right
        return equal if operator == "==" else not equal
    left_key = _version_key(left)
    right_key = _version_key(right)
    if left_key is None or right_key is None:
        raise InventoryMismatch("malformed_marker")
    width = max(len(left_key), len(right_key))
    padded_left = left_key + (0,) * (width - len(left_key))
    padded_right = right_key + (0,) * (width - len(right_key))
    if operator == ">=":
        return padded_left >= padded_right
    if operator == "<=":
        return padded_left <= padded_right
    if operator == ">":
        return padded_left > padded_right
    if operator == "<":
        return padded_left < padded_right
    if operator == "~=":
        return padded_left[: len(right_key) - 1] == padded_right[: len(right_key) - 1] and padded_left >= padded_right
    raise InventoryMismatch("malformed_marker")


def evaluate_marker(
    marker: str | None,
    *,
    extra: str = "",
    environment: Mapping[str, str | None] | None = None,
) -> bool | None:
    """Evaluate a marker for the Linux CPython 3.12 target.

    None means the marker depends on a value this stage does not know,
    such as the Python patch version. The host operating system is not used.
    """
    if marker is None:
        return True
    validate_marker(marker)
    env = dict(TARGET_ENVIRONMENT if environment is None else environment)
    env["extra"] = extra
    tokens = _tokens(marker.strip())
    value = _eval_or(tokens, env)
    if tokens:
        raise InventoryMismatch("malformed_marker")
    return value


def _lookup(token: str, env: Mapping[str, str | None]) -> object:
    if token.startswith(("'", '"')):
        return token[1:-1]
    if re.fullmatch(r"\d+(?:\.\d+)*", token):
        return token
    if token not in env:
        return _UNKNOWN
    value = env[token]
    if value is None:
        return _UNKNOWN
    return value


def _eval_or(tokens: list[str], env: Mapping[str, str | None]) -> bool | None:
    value = _eval_and(tokens, env)
    while tokens and tokens[0] == "or":
        tokens.pop(0)
        other = _eval_and(tokens, env)
        if value is True or other is True:
            value = True
        elif value is False and other is False:
            value = False
        else:
            value = None
    return value


def _eval_and(tokens: list[str], env: Mapping[str, str | None]) -> bool | None:
    value = _eval_not(tokens, env)
    while tokens and tokens[0] == "and":
        tokens.pop(0)
        other = _eval_not(tokens, env)
        if value is False or other is False:
            value = False
        elif value is True and other is True:
            value = True
        else:
            value = None
    return value


def _eval_not(tokens: list[str], env: Mapping[str, str | None]) -> bool | None:
    if not tokens:
        raise InventoryMismatch("malformed_marker")
    if tokens[0] == "not":
        tokens.pop(0)
        value = _eval_not(tokens, env)
        if value is None:
            return None
        return not value
    if tokens[0] == "(":
        tokens.pop(0)
        value = _eval_or(tokens, env)
        if not tokens or tokens.pop(0) != ")":
            raise InventoryMismatch("malformed_marker")
        return value
    return _eval_comparison(tokens, env)


def _eval_comparison(tokens: list[str], env: Mapping[str, str | None]) -> bool | None:
    if len(tokens) < 3:
        raise InventoryMismatch("malformed_marker")
    left, operator, right = tokens[:3]
    del tokens[:3]
    return _compare(_lookup(left, env), operator, _lookup(right, env))


def _split_marker(body: str) -> tuple[str, str | None]:
    single = False
    double = False
    for index, char in enumerate(body):
        if char == "'" and not double:
            single = not single
        elif char == '"' and not single:
            double = not double
        elif char == ";" and not single and not double:
            marker = body[index + 1 :].strip()
            if marker == "":
                raise InventoryMismatch("malformed_marker")
            return body[:index].strip(), marker
    return body.strip(), None


def _reject_directive(body: str) -> None:
    lowered = body.lower()
    if lowered.startswith(("-e ", "-e\t", "--editable")) or lowered == "-e":
        raise InventoryMismatch("editable_requirement")
    if lowered.startswith(("-r ", "-r\t", "--requirement")):
        raise InventoryMismatch("requirement_include")
    if lowered.startswith(("-c ", "-c\t", "--constraint")):
        raise InventoryMismatch("constraint_include")
    if lowered.startswith(("--index-url", "--extra-index-url", "-i ", "-i\t")):
        raise InventoryMismatch("index_override")
    if lowered.startswith(("--find-links", "-f ", "-f\t")):
        raise InventoryMismatch("find_links_override")
    if lowered.startswith("--trusted-host"):
        raise InventoryMismatch("trusted_host_override")
    if body.startswith("-"):
        raise InventoryMismatch("pip_option")
    if body.startswith(("./", ".\\", "/", "\\")) or (len(body) > 2 and body[1] == ":"):
        raise InventoryMismatch("local_path")


def _exactly_pinned(spec: str) -> bool:
    return re.fullmatch(r"==\s*[A-Za-z0-9.*+!_-]+", spec) is not None


def _upper_bound(spec: str) -> bool:
    return any(part.strip().startswith("<") for part in spec.split(",") if part.strip())


def parse_requirement_line(raw: str) -> dict[str, Any]:
    """Parse one requirement. Prohibited forms raise InventoryMismatch."""
    line = raw.strip()
    if not line or line.startswith("#"):
        raise InventoryMismatch("empty_requirement")
    body = line.split("#", 1)[0].strip()
    _reject_directive(body)
    requirement, marker = _split_marker(body)
    if "@" in requirement:
        _reject_reference(requirement)
    match = re.match(
        r"^(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
        r"(?:\[(?P<extras>[^\]]*)\])?"
        r"(?P<spec>.*)$",
        requirement,
    )
    if match is None or not NAME_RE.fullmatch(match.group("name")):
        raise InventoryMismatch("malformed_requirement")
    extras_text = match.group("extras")
    extras: list[str] = []
    if extras_text is not None:
        if extras_text.strip() == "":
            raise InventoryMismatch("malformed_requirement")
        for extra in extras_text.split(","):
            item = extra.strip()
            if not NAME_RE.fullmatch(item):
                raise InventoryMismatch("malformed_requirement")
            extras.append(item)
    spec = (match.group("spec") or "").strip()
    if spec and SPEC_RE.fullmatch(spec) is None:
        raise InventoryMismatch("malformed_requirement")
    if marker is not None:
        validate_marker(marker)
    name = match.group("name")
    return {
        "requirement_text": line,
        "normalized_name": normalize_name(name),
        "constraint": spec,
        "extras": extras,
        "environment_marker": marker,
        "exactly_pinned": _exactly_pinned(spec),
        "hashes_present": "--hash=" in line,
        "upper_bound": _upper_bound(spec),
        "native_extension_possible": normalize_name(name) in NATIVE,
        "transitive_dependencies_expected": True,
        "transitive_versions": "UNKNOWN",
        "source_distribution_could_be_selected": True,
        "source_class": "version_specifier",
    }


def _reject_reference(requirement: str) -> None:
    right = requirement.split("@", 1)[1].strip().lower()
    if right.startswith(("git+", "hg+", "svn+", "bzr+", "ssh:", "git:")):
        raise InventoryMismatch("vcs_requirement")
    if right.startswith(("https://", "http://", "file:", "ftp:")):
        raise InventoryMismatch("direct_url")
    raise InventoryMismatch("local_path")


def parse_requirement_document(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for raw in text.replace("\r\n", "\n").splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        row = parse_requirement_line(raw)
        key = str(row["normalized_name"])
        spec = str(row["constraint"])
        if key in seen:
            if seen[key] != spec:
                raise InventoryMismatch("conflicting_requirements")
            raise InventoryMismatch("duplicate_requirement")
        seen[key] = spec
        rows.append(row)
    return rows


def parse_requirements(text: str) -> list[dict[str, Any]]:
    """Parse the production direct-requirement file. It must contain nine lines."""
    rows = parse_requirement_document(text)
    if len(rows) != 9:
        raise InventoryMismatch(f"requirement_count:{len(rows)}")
    return rows
