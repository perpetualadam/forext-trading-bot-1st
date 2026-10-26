"""Offline classification of G.14.4 controls. Does not download or run pip."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_helper(name: str) -> str:
    return (ROOT / "tests" / name).read_text(encoding="utf-8")


def acquisition_controls(source: str) -> dict[str, str]:
    """Return IMPLEMENTED or MISSING from the acquisition helper source."""
    lowered = source.lower()
    return {
        "network_import": "ABSENT" if "import urllib" not in source and "import socket" not in source else "PRESENT",
        "subprocess": "ABSENT" if "import subprocess" not in source else "PRESENT",
        "pip_environment_isolation": "IMPLEMENTED" if "PIP_INDEX_URL" in source else "MISSING",
        "redirect_policy": "IMPLEMENTED" if "redirect" in lowered else "MISSING",
        "artifact_host_allowlist": "IMPLEMENTED" if "pythonhosted" in lowered else "MISSING",
        "wheels_only_flag": "IMPLEMENTED" if "--only-binary" in source else "MISSING",
        "symlink_check": "IMPLEMENTED" if "lstat" in source else "MISSING",
        "destination_guard": "IMPLEMENTED" if "def assert_destination_allowed" in source else "MISSING",
    }


def verifier_controls(source: str) -> dict[str, str]:
    return {
        "sha256": "IMPLEMENTED" if "hashlib.sha256" in source else "MISSING",
        "filename_tags": "IMPLEMENTED" if "def parse_wheel_filename" in source else "MISSING",
        "zip_archive": "IMPLEMENTED" if "import zipfile" in source else "MISSING",
        "wheel_metadata": "IMPLEMENTED" if "WHEEL" in source and "METADATA" in source else "MISSING",
        "record_member": "IMPLEMENTED" if "RECORD" in source else "MISSING",
        "decompression_limit": "IMPLEMENTED" if "compression" in source.lower() else "MISSING",
        "marker_evaluation": "IMPLEMENTED" if "sys_platform" in source else "MISSING",
    }


def inventory_controls(source: str) -> dict[str, str]:
    return {
        "hardcoded_empty_marker": "IMPLEMENTED" if '"environment_marker": None' in source else "MISSING",
        "direct_url_rejection": "IMPLEMENTED" if "direct_url" in source and "raise" in source else "MISSING",
        "vcs_rejection": "IMPLEMENTED" if "vcs" in source and "raise" in source else "MISSING",
    }
