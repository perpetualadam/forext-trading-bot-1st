"""Stage G.10 packaging review. Does not build an image or contact a broker."""

from __future__ import annotations

import ast
import ctypes
import hashlib
import json
import os
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from forex_bot.research.adaptive_ensemble.g4_integrity import git_baseline
from forex_bot.research.adaptive_ensemble.g8_dockerignore import (
    context_excluded,
    load_repo_rules,
)
from forex_bot.research.adaptive_ensemble.g10_snapshot import (
    ROOT,
    SNAPSHOT_ID,
    SnapshotBlocked,
    finalise_official,
    production_reachable,
    write_candidate,
)
from forex_bot.research.adaptive_ensemble.g10_verify import verify_archive

G10 = ROOT / "data" / "research" / "adaptive_ensemble" / "g10"
SAFETY_MODULES = (
    "forex_bot/app.py",
    "forex_bot/bot_loop.py",
    "forex_bot/live_safety.py",
    "forex_bot/market_provenance.py",
    "forex_bot/oanda_client.py",
    "forex_bot/oanda_exec.py",
    "forex_bot/live_manage.py",
    "forex_bot/decision_skip_log.py",
    "forex_bot/execution.py",
    "forex_bot/positions.py",
)
OFFLINE_FILES = {
    "forex_bot/backtest.py",
    "forex_bot/csv_ohlcv.py",
    "forex_bot/oanda_candles_read.py",
}
EXAMPLE_PASSWORD_KEY = "POSTGRES_PASSWORD"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _module_name(rel: str) -> str:
    if not rel.endswith(".py"):
        return ""
    name = rel[:-3].replace("/", ".")
    if name.endswith(".__init__"):
        return name[: -len(".__init__")]
    return name


def _imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _importers() -> dict[str, list[str]]:
    incoming: dict[str, list[str]] = {}
    for base in (ROOT / "forex_bot", ROOT / "tests"):
        if not base.is_dir():
            continue
        paths = base.rglob("*.py") if base.name == "forex_bot" else base.glob("*.py")
        for path in paths:
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            for imported in _imports(path):
                incoming.setdefault(imported, []).append(rel)
    return incoming


def _production_caller(rel: str) -> bool:
    if not rel.startswith("forex_bot/"):
        return False
    if "research/" in rel or "decision_quality/" in rel or "/shadow/" in rel:
        return False
    return rel not in OFFLINE_FILES


def _dynamic_sites() -> list[str]:
    sites: list[str] = []
    for path in (ROOT / "forex_bot").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            sites.append(path.relative_to(ROOT).as_posix() + ":unparsed")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            dynamic = isinstance(func, ast.Name) and func.id == "__import__"
            dynamic = dynamic or (isinstance(func, ast.Attribute) and func.attr == "import_module")
            if dynamic:
                sites.append(path.relative_to(ROOT).as_posix())
                break
    return sites


def dependency_audit() -> dict[str, Any]:
    reachable = production_reachable()
    incoming = _importers()
    rows: list[dict[str, str]] = []
    for path in sorted((ROOT / "forex_bot").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        module = _module_name(rel)
        callers = sorted(set(incoming.get(module, [])))
        production_callers = [item for item in callers if _production_caller(item)]
        if module in reachable:
            label = "PRODUCTION_REQUIRED"
            evidence = "static import reachable from forex_bot.app, forex_bot.bot_loop, or main"
        elif production_callers:
            label = "UNRESOLVED"
            evidence = "imported by production code outside the startup closure: " + ",".join(production_callers)
        elif rel == "forex_bot/decision_repair/harness.py":
            label = "TEST_ONLY"
            evidence = "imported by decision-repair tests; not by the production startup closure"
        elif rel == "forex_bot/live_safety_preflight.py":
            label = "OPTIONAL_OPERATIONAL_TOOL"
            evidence = "operator writer for durable blocked state; startup uses live_safety.initialise_fail_closed"
        elif rel in OFFLINE_FILES or rel.startswith(
            ("forex_bot/research/", "forex_bot/decision_quality/", "forex_bot/shadow/", "forex_bot/v2_shadow/")
        ):
            if rel.startswith("forex_bot/v2_shadow/") and module in reachable:
                label = "PRODUCTION_REQUIRED"
                evidence = "reachable"
            else:
                label = "RESEARCH_ONLY"
                evidence = "no import edge from the production startup closure"
        else:
            label = "UNRESOLVED"
            evidence = "no demonstrated importer; exclusion is not approved"
        rows.append({"path": rel, "classification": label, "evidence": evidence, "module": module})
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    dynamic = _dynamic_sites()
    dynamic_in_closure = [
        site
        for site in dynamic
        if _module_name(site.split(":")[0]) in reachable
    ]
    unresolved = [row["path"] for row in rows if row["classification"] == "UNRESOLVED"]
    return {
        "counts": counts,
        "dynamic_import_sites": dynamic,
        "dynamic_imports_in_production_closure": dynamic_in_closure,
        "modules": rows,
        "production_required": [row["path"] for row in rows if row["classification"] == "PRODUCTION_REQUIRED"],
        "research_only": [row["path"] for row in rows if row["classification"] == "RESEARCH_ONLY"],
        "unresolved": unresolved,
        "closure_resolved": not unresolved and not dynamic_in_closure,
    }


def proposed_allowlist(audit: dict[str, Any]) -> dict[str, Any]:
    required = set(audit["production_required"])
    packaging = ["Dockerfile", ".dockerignore", "main.py", "requirements.txt"]
    included = sorted(required | set(packaging))
    missing_safety = [path for path in SAFETY_MODULES if path not in required]
    rows = []
    for rel in included:
        data = (ROOT / rel).read_bytes()
        reason = "startup closure" if rel in required else "image entry or build instruction"
        rows.append(
            {
                "path": rel,
                "sha256": _sha256(data),
                "size": len(data),
                "reason": reason,
                "safety_critical": rel in SAFETY_MODULES or rel == "main.py",
            }
        )
    approved = audit["closure_resolved"] and not missing_safety
    return {
        "status": "PROPOSED_NOT_APPLIED" if approved else "NOT_APPROVED",
        "image_build_authorised": False,
        "dockerfile_still_copies_entire_package": True,
        "files": rows,
        "missing_safety_modules": missing_safety,
        "file_count": len(rows),
    }


def exclusion_inventory(audit: dict[str, Any], allowlist: dict[str, Any]) -> list[dict[str, str]]:
    included = {row["path"] for row in allowlist["files"]}
    rows: list[dict[str, str]] = []
    for row in audit["modules"]:
        if row["path"] in included:
            continue
        rows.append(
            {
                "path": row["path"],
                "reason": row["classification"],
                "evidence": row["evidence"],
                "limitation": "static import analysis; a string-loaded plugin would not be visible",
            }
        )
    rows.extend(
        [
            {"path": ".env", "reason": "secret", "evidence": "dockerignore and snapshot name rule", "limitation": "local matcher is not the Docker daemon"},
            {"path": "data/", "reason": "operational_state_and_research_data", "evidence": "dockerignore /data", "limitation": "compose still bind-mounts data/ops at runtime"},
            {"path": "tests/", "reason": "test_only", "evidence": "not copied by the Dockerfile", "limitation": "none"},
            {"path": "docker-compose.yml", "reason": "compose_not_image_source", "evidence": "dockerignore excludes it; reviewed snapshot still contains it", "limitation": "runtime mounts are outside the image"},
            {"path": ".env.example", "reason": "template_not_runtime", "evidence": "not imported; example password is disclosed by length only", "limitation": "must not be treated as a live credential"},
        ]
    )
    return rows


def _reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    if attrs == 0xFFFFFFFF:
        return False
    return bool(attrs & 0x400)


def link_scan() -> dict[str, Any]:
    links: list[str] = []
    scanned = 0
    for base in (ROOT / "forex_bot", ROOT):
        candidates = base.rglob("*") if base.name == "forex_bot" else [path for path in base.iterdir()]
        for path in candidates:
            if path.name in {".git", ".venv", "venv", "data"} and base == ROOT:
                continue
            scanned += 1
            try:
                if _reparse(path):
                    links.append(path.relative_to(ROOT).as_posix())
            except OSError:
                links.append(path.relative_to(ROOT).as_posix() + ":unreadable")
    return {
        "scanned_entries": scanned,
        "links": links,
        "unsafe_links_in_snapshot_input": links,
        "windows_reparse_limitation": "GetFileAttributesW reparse bit is checked for forex_bot and the repository root. Junctions inside skipped data/ and .git are not enumerated. A reparse point that is not also a Python symlink can still be invisible to pathlib.is_symlink.",
    }


SECRET_KEYS = {
    "OANDA_ACCESS_TOKEN",
    "OANDA_API_KEY",
    "OANDA_ACCOUNT_ID",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "TELEGRAM_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TRADING_ECONOMICS_API_KEY",
    "POSTGRES_PASSWORD",
}


def _assignment_findings(rel: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    encoded = text.encode("utf-8")
    if (b"BEGIN " + b"PRIVATE KEY") in encoded:
        findings.append({"path": rel, "category": "private_key", "template": False, "blocking": True, "detail": "banner"})
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        label = key.strip()
        if label not in SECRET_KEYS or not raw_value.strip():
            continue
        if any(token in raw_value for token in ("getenv", "environ", "os.environ")):
            continue
        value = raw_value.strip().strip("'\"")
        if rel == ".env.example" and label == EXAMPLE_PASSWORD_KEY:
            findings.append(
                {
                    "path": rel,
                    "category": "example_database_password",
                    "template": True,
                    "blocking": False,
                    "detail": "len=" + str(len(value)),
                }
            )
            continue
        findings.append(
            {
                "path": rel,
                "category": "credential_assignment",
                "template": rel.endswith(".example"),
                "blocking": True,
                "detail": "nonempty_assignment:" + label,
            }
        )
    return findings


def secret_scan(paths: list[str]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for rel in paths:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        findings.extend(_assignment_findings(rel, text))
    return {
        "files_scanned": len(paths),
        "findings": findings,
        "blocking": [row["path"] for row in findings if row["blocking"]],
        "values_printed": False,
    }


def build_context_audit(allowlist: dict[str, Any]) -> dict[str, Any]:
    rules = load_repo_rules(ROOT)
    probes = {
        ".env": True,
        ".env.local": True,
        "id_rsa": True,
        "credentials.json": True,
        "secrets/token.pem": True,
        "data/ops/live_safety_state.json": True,
        "data/research/adaptive_ensemble/g3/normalised/EUR_USD_M5.csv": True,
        "data/research/adaptive_ensemble/g7/source_snapshot.tar": True,
        "data/research/adaptive_ensemble/g10/source_snapshot.tar": True,
        "tests/test_g10_snapshot.py": True,
        ".git/config": True,
        "forex_bot/bot_loop.py": False,
        "forex_bot/live_safety.py": False,
        "main.py": False,
        "requirements.txt": False,
        ".env.example": False,
        "docker-compose.yml": True,
    }
    checked = {path: context_excluded(path, rules) for path in probes}
    mismatches = [path for path, expected in probes.items() if checked[path] != expected]
    retained = []
    for row in allowlist["files"]:
        retained.append({"path": row["path"], "excluded_by_local_matcher": context_excluded(row["path"], rules)})
    dropped = [row["path"] for row in retained if row["excluded_by_local_matcher"]]
    return {
        "context_root": ".",
        "matcher": "g8_dockerignore.context_excluded",
        "daemon_verified": False,
        "probes": checked,
        "probe_mismatches": mismatches,
        "allowlist_excluded_by_matcher": dropped,
        "dockerfile_copy": ["requirements.txt", "forex_bot/", "main.py"],
        "compose_bind_mounts_not_removed": ["data/ops", "data/research/v2_shadow"],
    }


def proposed_dockerfile_patch(allowlist: dict[str, Any]) -> str:
    lines = [
        "# REVIEW ARTIFACT ONLY. Do not apply. Do not build.",
        "# Replaces COPY forex_bot/ with the proposed production allowlist.",
        "--- a/Dockerfile",
        "+++ b/Dockerfile",
        "@@",
        "-COPY forex_bot ./forex_bot",
        "-COPY main.py .",
    ]
    for row in allowlist["files"]:
        if row["path"] in {"Dockerfile", ".dockerignore", "requirements.txt"}:
            continue
        lines.append("+COPY " + row["path"] + " ./" + row["path"])
    lines.append("+COPY main.py .")
    return "\n".join(lines) + "\n"


def repair_markers(tar_path: Path) -> dict[str, bool]:
    with tarfile.open(tar_path, "r:") as archive:
        handle = archive.extractfile("forex_bot/bot_loop.py")
        if handle is None:
            return {"present": False}
        text = handle.read().decode("utf-8")
    return {
        "present": True,
        "contain_candle_exception": "_contain_candle_exception" in text,
        "cycle_integrity_error": "class CycleIntegrityError" in text,
        "assertion_reraise": "except AssertionError:" in text,
        "management_continued": "management_continued_without_candles" in text,
        "early_return_removed": "if raw is None or raw.empty:" not in text,
    }


def write_review_artifacts(
    manifest: dict[str, Any],
    verification: dict[str, Any],
    regeneration_identical: bool,
) -> dict[str, Any]:
    audit = dependency_audit()
    allow = proposed_allowlist(audit)
    excluded = exclusion_inventory(audit, allow)
    links = link_scan()
    paths = [row["path"] for row in manifest["files"]]
    secrets = secret_scan(paths)
    context = build_context_audit(allow)
    git = git_baseline()
    prefixes: dict[str, int] = {}
    for line in git["porcelain"]:
        path = line[3:] if len(line) > 3 else line
        top = path.split("/", 1)[0].strip()
        prefixes[top] = prefixes.get(top, 0) + 1
    inventory = {
        "snapshot_id": SNAPSHOT_ID,
        "git_head": git["revision"],
        "working_tree_dirty": git["porcelain_count"] > 0,
        "porcelain_count": git["porcelain_count"],
        "porcelain_prefix_counts": prefixes,
        "git_identity_is_not_snapshot_identity": True,
        "source_file_count": manifest["source_file_count"],
        "payload_bytes": manifest["payload_bytes"],
        "manifest_sha256": manifest["manifest_sha256"],
        "archive_sha256": verification.get("archive_sha256"),
        "included_paths": paths,
        "classifications": {
            row["path"]: row["classification"] for row in manifest["files"]
        },
    }
    patch = proposed_dockerfile_patch(allow)
    (G10 / "source_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (G10 / "production_dependency_audit.json").write_text(
        json.dumps({key: value for key, value in audit.items() if key != "modules"}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (G10 / "production_dependency_graph.json").write_text(
        json.dumps(audit["modules"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (G10 / "production_allowlist.json").write_text(json.dumps(allow, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (G10 / "research_exclusion.json").write_text(json.dumps(excluded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (G10 / "build_context_audit.json").write_text(json.dumps(context, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (G10 / "symlink_assessment.json").write_text(json.dumps(links, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (G10 / "security_scan.json").write_text(json.dumps(secrets, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (G10 / "proposed_dockerfile.patch").write_text(patch, encoding="utf-8")
    (G10 / "packaging_policy.json").write_text(
        json.dumps(
            {
                "snapshot_id": SNAPSHOT_ID,
                "reviewed_snapshot_includes_research_source": True,
                "proposed_image_excludes_research_source": allow["status"] != "NOT_APPROVED",
                "dockerfile_modified": False,
                "dockerignore_modified": False,
                "image_build_authorised": False,
                "allowlist_status": allow["status"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "audit": audit,
        "allowlist": allow,
        "secrets": secrets,
        "links": links,
        "context": context,
        "inventory": inventory,
        "regeneration_identical": regeneration_identical,
    }


EXPECTED_HEAD = "f6c4f40ae6b7614379347ed45141ecd5a3d33642"
EXPECTED_AUTH_AT = "2026-10-08T22:24:23.529484+00:00"


def _auth_evidence() -> dict[str, Any]:
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    auth = document.get("live_order_authorisation")
    if not isinstance(auth, dict):
        raise SnapshotBlocked("BASELINE_INTEGRITY_BLOCKED")
    strategies = document.get("strategies")
    if not isinstance(strategies, dict):
        raise SnapshotBlocked("BASELINE_INTEGRITY_BLOCKED")
    active = sorted(name for name, row in strategies.items() if isinstance(row, dict) and row.get("active"))
    return {
        "state": auth.get("state"),
        "reason": auth.get("reason"),
        "updated_at_utc": auth.get("updated_at_utc"),
        "strategy_count": len(strategies),
        "active_strategies": active,
    }


def publish_once() -> dict[str, Any]:
    """Freeze the official archive once. Tests must not call this."""
    if (G10 / "source_snapshot.tar").exists():
        raise SnapshotBlocked("official_snapshot_already_frozen")
    G10.mkdir(parents=True, exist_ok=True)
    git = git_baseline()
    auth = _auth_evidence()
    if git["revision"] != EXPECTED_HEAD or git["porcelain_count"] == 0:
        raise SnapshotBlocked("BASELINE_INTEGRITY_BLOCKED")
    if auth["state"] != "BLOCKED" or auth["reason"] != "operator_preflight_blocked":
        raise SnapshotBlocked("BASELINE_INTEGRITY_BLOCKED")
    if auth["updated_at_utc"] != EXPECTED_AUTH_AT or auth["strategy_count"] != 6 or auth["active_strategies"]:
        raise SnapshotBlocked("BASELINE_INTEGRITY_BLOCKED")
    prefixes: dict[str, int] = {}
    for line in git["porcelain"]:
        path = line[3:] if len(line) > 3 else line
        prefixes[path.split("/", 1)[0].strip()] = prefixes.get(path.split("/", 1)[0].strip(), 0) + 1
    baseline = {
        "git_head": git["revision"],
        "porcelain_count": git["porcelain_count"],
        "porcelain_prefix_counts": prefixes,
        "working_tree_dirty": True,
        "live_order_authorisation": auth,
        "expected_head_matches": True,
    }
    (G10 / "baseline_integrity.json").write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
        first_root = Path(first_dir)
        second_root = Path(second_dir)
        candidate = write_candidate(first_root / "source_snapshot.tar", first_root / "source_manifest.json")
        write_candidate(second_root / "source_snapshot.tar", second_root / "source_manifest.json")
        first_bytes = (first_root / "source_snapshot.tar").read_bytes()
        second_bytes = (second_root / "source_snapshot.tar").read_bytes()
        first_manifest_text = (first_root / "source_manifest.json").read_text(encoding="utf-8")
        second_manifest_text = (second_root / "source_manifest.json").read_text(encoding="utf-8")
        if first_bytes != second_bytes or first_manifest_text != second_manifest_text:
            raise SnapshotBlocked("SNAPSHOT_REPRODUCIBILITY_BLOCKED")
        preview = verify_archive(first_root / "source_snapshot.tar", first_root / "source_manifest.json")
        if not preview["ok"]:
            raise SnapshotBlocked("SOURCE_SNAPSHOT_INTEGRITY_FAILED")
        secrets = secret_scan([row["path"] for row in candidate["files"]])
        links = link_scan()
        if secrets["blocking"] or links["links"]:
            raise SnapshotBlocked("SOURCE_SNAPSHOT_INTEGRITY_FAILED")
    manifest = finalise_official()
    official_bytes = (G10 / "source_snapshot.tar").read_bytes()
    if official_bytes != first_bytes:
        raise SnapshotBlocked("SOURCE_SNAPSHOT_INTEGRITY_FAILED")
    verified = verify_archive(G10 / "source_snapshot.tar", G10 / "source_manifest.json")
    if not verified["ok"]:
        raise SnapshotBlocked("SOURCE_SNAPSHOT_INTEGRITY_FAILED")
    write_review_artifacts(manifest, verified, True)
    markers = repair_markers(G10 / "source_snapshot.tar")
    verification = {
        "snapshot_id": SNAPSHOT_ID,
        "archive_sha256": verified["archive_sha256"],
        "manifest_sha256": verified["manifest_sha256"],
        "file_count": verified["file_count"],
        "payload_bytes": verified["payload_bytes"],
        "format": verified["format"],
        "independent_verification": True,
        "regeneration_identical": True,
        "repair_markers": markers,
        "sensitive_files_included": False,
        "operational_state_included": False,
    }
    (G10 / "snapshot_verification.json").write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return verification
