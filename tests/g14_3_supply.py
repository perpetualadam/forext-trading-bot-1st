"""Offline supply-chain checks for Stage G.14.3. No downloads and no Docker."""

from __future__ import annotations

import re
from typing import Any

NATIVE_EXTENSION_PACKAGES = frozenset({"numpy", "pandas", "psycopg2-binary"})
REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[(?P<extras>[^\]]+)\])?(?P<spec>.*)$"
)


def parse_requirements(text: str) -> list[dict[str, Any]]:
    """Parse direct requirements. Transitive versions are never invented."""
    records: list[dict[str, Any]] = []
    for raw in text.replace("\r\n", "\n").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        marker = None
        if ";" in line:
            line, marker = (part.strip() for part in line.split(";", 1))
        url = None
        if " @" in line or line.startswith(("git+", "http://", "https://")):
            url = line
        match = REQUIREMENT_RE.match(line)
        if match is None:
            raise ValueError(f"unsupported requirement: {line}")
        name = match.group("name")
        extras = [item.strip() for item in (match.group("extras") or "").split(",") if item.strip()]
        spec = (match.group("spec") or "").strip()
        hashes = "--hash=" in raw
        native = name.lower() in NATIVE_EXTENSION_PACKAGES
        records.append(
            {
                "name": name,
                "constraint": spec or None,
                "extras": extras,
                "environment_marker": marker,
                "direct_url": url,
                "exactly_pinned": _exactly_pinned(spec),
                "range_kind": _range_kind(spec),
                "hashes_specified": hashes,
                "may_introduce_transitive_dependencies": True,
                "transitive_versions": "UNKNOWN",
                "platform_specific_wheels_possible": native,
                "python_version_dependent_resolution": "UNKNOWN",
                "source_distribution_fallback_possible": True,
                "native_extension_risk": native,
                "may_require_build_tools_on_source_fallback": native,
                "installation_hooks_possible": True,
            }
        )
    return records


def _exactly_pinned(spec: str) -> bool:
    return spec.startswith("==") and "," not in spec and "*" not in spec and spec != "=="


def _range_kind(spec: str) -> str:
    if _exactly_pinned(spec):
        return "exact_pin"
    if spec.startswith("~="):
        return "compatible_release"
    if spec.startswith((">=", ">")):
        upper = any(token in spec for token in (",<", ",<="))
        return "bounded_range" if upper else "minimum_unbounded"
    if not spec:
        return "unconstrained"
    return "other"


def inventory_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "direct_requirement_count": len(records),
        "exact_pins": sum(1 for row in records if row["exactly_pinned"]),
        "minimum_unbounded": sum(1 for row in records if row["range_kind"] == "minimum_unbounded"),
        "compatible_releases": sum(1 for row in records if row["range_kind"] == "compatible_release"),
        "missing_hashes": sum(1 for row in records if not row["hashes_specified"]),
        "transitive_versions": "UNKNOWN",
        "native_extension_packages": [row["name"] for row in records if row["native_extension_risk"]],
        "complete_transitive_lock": False,
        "verified_hashes": False,
        "verified_wheelhouse": False,
    }


def lock_claim_problems(claim: dict[str, Any]) -> list[str]:
    """Reject a lock claim that goes beyond the evidence it carries."""
    problems: list[str] = []
    if claim.get("claims_complete_transitive_lock") and claim.get("transitive_versions") == "UNKNOWN":
        problems.append("fabricated_completeness")
    hashes = claim.get("hashes") or []
    if claim.get("claims_hashes_verified") and not hashes:
        problems.append("missing_hashes")
    image_id = str(claim.get("image_id") or "")
    digest = str(claim.get("registry_digest") or "")
    image_hex = image_id.removeprefix("sha256:")
    digest_hex = digest.split("@sha256:")[-1] if "@sha256:" in digest else digest.removeprefix("sha256:")
    presented_as_registry = bool(claim.get("claims_registry_digest_verified"))
    same_value = bool(image_hex) and image_hex == digest_hex
    has_registry = "/" in digest.split("@", 1)[0]
    if presented_as_registry and (not digest or same_value or not has_registry):
        problems.append("unknown_base_digest_claim")
    return problems


def classify_base_identity(image_id: str, repo_digests: list[str]) -> dict[str, Any]:
    image_hex = image_id.removeprefix("sha256:")
    same = [item for item in repo_digests if item.split("@sha256:")[-1] == image_hex]
    registry = [item for item in repo_digests if "/" in item.split("@", 1)[0]]
    distinct = [item for item in repo_digests if item.split("@sha256:")[-1] != image_hex]
    return {
        "local_image_id": image_id,
        "repository_tag_is_mutable": True,
        "registry_manifest_digest_known": bool(distinct and registry),
        "repo_digest_repeats_image_id": bool(same),
        "configuration_digest_separately_recorded": False,
        "multi_platform_manifest_list_digest": "UNKNOWN",
        "platform_specific_manifest_digest": "UNKNOWN",
        "immutable_from_reference_available": False,
        "classification": "BASE_IMAGE_DIGEST_UNVERIFIED",
    }


def pip_toolchain_findings(dockerfile: str) -> dict[str, Any]:
    text = dockerfile.replace("\r\n", "\n")
    upgrades = "pip install --upgrade pip" in text
    pinned = "pip install --upgrade pip==" in text or "pip==" in text
    return {
        "upgrades_pip_without_exact_pin": upgrades and not pinned,
        "known_pip_version": "UNKNOWN",
        "resolution_behavior_may_change": True,
        "may_contact_package_index": True,
        "classification": "PIP_TOOLCHAIN_VERSION_UNVERIFIED",
    }


def source_fallback_allowed(dockerfile: str) -> bool:
    text = dockerfile.replace("\r\n", "\n")
    return "--prefer-binary" in text and "--only-binary" not in text


def previous_command_recommendation(command: str) -> str:
    """The recorded build command is not a reproducible build."""
    uses_staged_context = "forext-g14-1-staging" in command
    refreshes_nothing = "--pull=false" in command
    if uses_staged_context and refreshes_nothing:
        return "REPLACE_WITH_LOCKED_OFFLINE_BUILD_PROPOSAL"
    return "BUILD_PROPOSAL_BLOCKED"
