"""Create the G.14.1 staging directory once. Does not invoke Docker."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "adaptive_ensemble" / "g14_1"
DOCKERFILE_SHA = "4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad"
DOCKERIGNORE_SHA = "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd"
ALLOWLIST_SHA = "b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4"
HEAD = "d080d897945bc44fa37c02caab504ed707146bec"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tests" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if _sha(ROOT / "Dockerfile") != DOCKERFILE_SHA:
        raise SystemExit("dockerfile hash drifted")
    if _sha(ROOT / ".dockerignore") != DOCKERIGNORE_SHA:
        raise SystemExit("dockerignore hash drifted")
    allow_path = ROOT / "data/research/adaptive_ensemble/g10/production_allowlist.json"
    if _sha(allow_path) != ALLOWLIST_SHA:
        raise SystemExit("allowlist hash drifted")
    payload = json.loads(allow_path.read_text(encoding="utf-8"))
    stage = _load("g14_1_stage")
    verify = _load("g14_1_verify")
    sys.path.insert(0, str(ROOT))
    from forex_bot.research.adaptive_ensemble.g8_dockerignore import (
        load_repo_rules,
    )

    paths = [row["path"] for row in payload["files"]]
    hashes = {row["path"]: row["sha256"] for row in payload["files"]}
    counts: dict[str, int] = {}
    for path in paths:
        kind = stage.classify_path(path)
        counts[kind] = counts.get(kind, 0) + 1
    parent = Path(tempfile.gettempdir())
    if "OneDrive" in parent.parts:
        raise SystemExit("temp directory is inside OneDrive")
    staging = Path(tempfile.mkdtemp(prefix="forext-g14-1-staging-", dir=parent))
    result = stage.stage_context(
        ROOT,
        paths,
        hashes,
        authorised_dockerfile_sha256=DOCKERFILE_SHA,
        dockerignore_sha256=DOCKERIGNORE_SHA,
        output_dir=staging,
        dockerignore_rules=load_repo_rules(ROOT),
    )
    checked = verify.verify_directory(staging, result["files"], dockerignore_rules=load_repo_rules(ROOT))
    canonical = json.dumps({"files": result["files"]}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    info = staging.stat()
    manifest = {
        "manifest_sha256": digest,
        "digest_covers": "canonical JSON of the files array only",
        "total_files": len(result["files"]),
        "total_bytes": sum(row["size"] for row in result["files"]),
        "staging_directory": str(staging),
        "outside_onedrive": "OneDrive" not in staging.resolve().parts,
        "verification_timestamp": datetime.now(UTC).isoformat(),
        "git_head": HEAD,
        "dockerfile_sha256": DOCKERFILE_SHA,
        "dockerignore_sha256": DOCKERIGNORE_SHA,
        "allowlist_sha256": ALLOWLIST_SHA,
        "independent_verification": checked["independent_verification"],
        "docker_daemon_context_behaviour": checked["docker_daemon_context_behaviour"],
        "directory_permissions": stat.filemode(info.st_mode),
        "files": result["files"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "staged_context_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    summary = {
        "counts": counts,
        "allowlist_paths": len(paths),
        "application_files": counts["PYTHON_PACKAGE_FILE"] + counts["APPLICATION_ENTRYPOINT"] + counts["DEPENDENCY_MANIFEST"],
        "context_files": len(result["files"]),
        "policy_files_not_copied": counts["DOCKERFILE"] + counts["DOCKERIGNORE"],
        "opened_paths": result["opened_paths"],
        "staging_directory": str(staging),
        "historical_dockerfile_sha256": hashes["Dockerfile"],
        "independent_verification": checked,
    }
    (OUT / "_stage_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(staging)
    print(digest)
    print(manifest["total_files"], manifest["total_bytes"])


if __name__ == "__main__":
    main()
