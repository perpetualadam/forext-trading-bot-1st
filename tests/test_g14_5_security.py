"""Security tests against the real G.14.4 helpers. Gaps stay visible."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NINE = """
python-dotenv>=1.0.0
pandas>=2.0.0
numpy>=1.24.0
requests @ https://files.example/requests.whl
psycopg2-binary>=2.9.9
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
oandapyV20>=0.7.2
tzdata>=2024.1 ; sys_platform == "linux"
"""
VCS_NINE = NINE.replace(
    "pandas>=2.0.0",
    "pandas @ git+https://example.invalid/pandas.git",
)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _load("g14_5_audit")
ACQUIRE = _load("g14_4_acquire")
VERIFY = _load("g14_4_verify")
INVENTORY = _load("g14_4_inventory")


def test_import_has_no_network_client() -> None:
    for name in ("g14_4_acquire.py", "g14_4_verify.py", "g14_4_inventory.py"):
        source = Path(__file__).with_name(name).read_text(encoding="utf-8")
        for banned in ("import urllib", "import socket", "import subprocess", "import docker", "import requests"):
            assert banned not in source


def test_acquisition_helper_does_not_enforce_network_policy() -> None:
    """Migrated in G.14.6 from a gap assertion to the repaired controls."""
    controls = AUDIT.acquisition_controls(AUDIT.read_helper("g14_4_acquire.py"))
    assert controls["network_import"] == "ABSENT"
    assert controls["subprocess"] == "ABSENT"
    assert controls["pip_environment_isolation"] == "IMPLEMENTED"
    assert controls["redirect_policy"] == "IMPLEMENTED"
    assert controls["artifact_host_allowlist"] == "IMPLEMENTED"
    assert controls["wheels_only_flag"] == "IMPLEMENTED"
    assert controls["symlink_check"] == "IMPLEMENTED"
    assert controls["destination_guard"] == "IMPLEMENTED"
    with __import__("pytest").raises(ACQUIRE.PolicyRejected):
        ACQUIRE.authorize_redirect_chain(
            ["https://pypi.org/simple", "https://evil.example/demo.whl"],
            role="index",
        )


def test_inherited_pip_settings_are_not_filtered() -> None:
    """Migrated in G.14.6. Inherited names are rejected instead of copied."""
    basics = {"SYSTEMROOT": r"C:\Windows", "WINDIR": r"C:\Windows"}
    interpreter = Path(r"C:\synthetic\python.exe")
    for name in (
        "PIP_INDEX_URL",
        "PIP_EXTRA_INDEX_URL",
        "PIP_FIND_LINKS",
        "PIP_TRUSTED_HOST",
        "PIP_CONFIG_FILE",
        "PIP_PRE",
        "PIP_NO_BINARY",
        "PIP_ONLY_BINARY",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
        "REQUESTS_CA_BUNDLE",
    ):
        with __import__("pytest").raises(ACQUIRE.EnvironmentRejected):
            ACQUIRE.build_acquisition_environment(
                {name: "synthetic-unapproved"},
                interpreter=interpreter,
                platform_basics=basics,
            )
    clean = ACQUIRE.build_acquisition_environment({}, interpreter=interpreter, platform_basics=basics)
    assert "PIP_INDEX_URL" not in clean
    assert clean["PIP_ONLY_BINARY"] == ":all:"


def test_inventory_accepts_direct_url_vcs_and_drops_markers() -> None:
    """Migrated in G.14.6. Those forms are now rejected and markers are kept."""
    with __import__("pytest").raises(INVENTORY.InventoryMismatch, match="direct_url"):
        INVENTORY.parse_requirements(NINE)
    with __import__("pytest").raises(INVENTORY.InventoryMismatch, match="vcs_requirement"):
        INVENTORY.parse_requirements(VCS_NINE)
    marked = INVENTORY.parse_requirement_line('tzdata>=2024.1 ; sys_platform == "linux"')
    assert marked["environment_marker"] == 'sys_platform == "linux"'
    assert AUDIT.inventory_controls(AUDIT.read_helper("g14_4_inventory.py"))["direct_url_rejection"] == "IMPLEMENTED"
    assert AUDIT.inventory_controls(AUDIT.read_helper("g14_4_inventory.py"))["vcs_rejection"] == "IMPLEMENTED"


def test_verifier_hash_does_not_require_a_zip_archive(tmp_path: Path) -> None:
    content = b"this-is-not-a-zip"
    filename = "demo-1.0.0-py3-none-any.whl"
    package = {
        "name": "demo",
        "version": "1.0.0",
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
    manifest = {
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
        "packages": [package],
        "toolchain": {"pip_version": "UNKNOWN", "resolver": "UNKNOWN"},
        "claimed_state": None,
    }
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    (wheelhouse / filename).write_bytes(content)
    with __import__("pytest").raises(VERIFY.VerificationRejected, match="malformed_zip"):
        VERIFY.verify_wheelhouse(manifest, wheelhouse)
    controls = AUDIT.verifier_controls(AUDIT.read_helper("g14_4_verify.py"))
    assert controls["sha256"] == "IMPLEMENTED"
    assert controls["zip_archive"] == "IMPLEMENTED"
    assert controls["wheel_metadata"] == "IMPLEMENTED"
    assert controls["record_member"] == "IMPLEMENTED"
    assert controls["decompression_limit"] == "IMPLEMENTED"
    assert controls["marker_evaluation"] == "IMPLEMENTED"


def test_verifier_still_rejects_provenance_and_completion_claims(tmp_path: Path) -> None:
    content = b"synthetic-wheel\n"
    filename = "demo-1.0.0-py3-none-any.whl"
    package = {
        "name": "demo",
        "version": "1.0.0",
        "filename": filename,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
        "direct": True,
        "extras": [],
        "markers": None,
        "requires": ["missing"],
        "provenance": "synthetic-fixture",
        "url": None,
        "vcs": None,
    }
    manifest = {
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
        "packages": [package],
        "toolchain": {"pip_version": "UNKNOWN", "resolver": "UNKNOWN"},
        "claimed_state": "INDEPENDENT_ARTIFACT_VERIFICATION_COMPLETE",
    }
    with __import__("pytest").raises(VERIFY.VerificationRejected, match="false_completion_claim"):
        VERIFY.verify_wheelhouse(manifest, tmp_path)
    manifest["claimed_state"] = None
    wheelhouse = tmp_path / "present"
    wheelhouse.mkdir()
    (wheelhouse / filename).write_bytes(content)
    with __import__("pytest").raises(VERIFY.VerificationRejected, match="missing_dependency"):
        VERIFY.verify_wheelhouse(manifest, wheelhouse)


def test_destination_guard_does_not_cover_outside_writes_by_itself(tmp_path: Path) -> None:
    """Migrated in G.14.6. The destination check now rejects links before resolve."""
    allowed = tmp_path / "empty-candidate"
    allowed.mkdir()
    ACQUIRE.assert_destination_allowed(allowed)
    assert "lstat" in AUDIT.read_helper("g14_4_acquire.py")
    assert not hasattr(ACQUIRE, "resolve_and_follow")
