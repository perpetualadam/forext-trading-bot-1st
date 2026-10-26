"""Offline Stage G.13 packaging checks. No Docker daemon, broker, or database."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = ROOT / "data" / "research" / "adaptive_ensemble" / "g10" / "production_allowlist.json"
DOCKERIGNORE = ROOT / ".dockerignore"

POLICY_NOT_COPIED = frozenset({"Dockerfile", ".dockerignore"})
ENTRYPOINT = 'CMD ["uvicorn", "forex_bot.app:app", "--host", "0.0.0.0", "--port", "8000"]'
PIP_COMMAND = (
    "RUN pip install --upgrade pip && \\\n"
    "    pip install --no-cache-dir --prefer-binary --timeout 120 --retries 15 -r requirements.txt"
)
FROM_LINE = "FROM python:3.12-slim-bookworm"
WORKDIR_LINE = "WORKDIR /app"
REPARSE_POINT = 0x400
ENTRY_MODULES = ("main.py", "forex_bot/app.py")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_allowlist(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or ALLOWLIST_PATH).read_text(encoding="utf-8"))


def allowlist_paths(document: dict[str, Any]) -> list[str]:
    return [str(row["path"]) for row in document["files"]]


def application_copy_paths(paths: list[str]) -> list[str]:
    return sorted(path for path in paths if path not in POLICY_NOT_COPIED)


def is_reparse_point(path: Path) -> bool:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & REPARSE_POINT)


def render_dockerfile(paths: list[str]) -> str:
    copies = ["COPY requirements.txt ."]
    for rel in application_copy_paths(paths):
        if rel == "requirements.txt":
            continue
        destination = f"./{rel}" if rel != "main.py" else "./main.py"
        copies.append(f"COPY {rel} {destination}")
    body = "\n".join(
        [
            "# Forex bot + FastAPI dashboard",
            FROM_LINE,
            "",
            WORKDIR_LINE,
            "",
            "ENV PYTHONDONTWRITEBYTECODE=1 \\",
            "    PYTHONUNBUFFERED=1 \\",
            "    PIP_DISABLE_PIP_VERSION_CHECK=1 \\",
            "    PIP_DEFAULT_TIMEOUT=120 \\",
            "    PIP_RETRIES=15",
            "",
            *copies[:1],
            PIP_COMMAND,
            "",
            "# Production application files: explicit audited allowlist.",
            *copies[1:],
            "",
            "EXPOSE 8000",
            "",
            "# Single worker: bot loop runs in-process via FastAPI lifespan (do not scale replicas blindly).",
            ENTRYPOINT,
            "",
        ]
    )
    return body.replace("\n", "\r\n")


def parse_copies(dockerfile: str) -> list[tuple[str, str]]:
    copies: list[tuple[str, str]] = []
    for raw in dockerfile.replace("\r\n", "\n").splitlines():
        line = raw.strip()
        if not line.startswith("COPY "):
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f"unsupported COPY form: {line}")
        copies.append((parts[1], parts[2]))
    return copies


def _destination(source: str, dest: str) -> str:
    if dest in {".", "./"}:
        name = Path(source).name
        return f"/app/{name}"
    if dest.startswith("/"):
        return Path(dest).as_posix()
    return Path("/app", dest).as_posix()


def _escapes_app(destination: str) -> bool:
    resolved = Path(destination).as_posix()
    return resolved != "/app" and not resolved.startswith("/app/")


def dockerignore_rules() -> list[dict[str, Any]]:
    from forex_bot.research.adaptive_ensemble.g8_dockerignore import load_repo_rules

    return load_repo_rules(ROOT)


def source_excluded(rel: str, rules: list[dict[str, Any]] | None = None) -> bool:
    from forex_bot.research.adaptive_ensemble.g8_dockerignore import context_excluded

    return context_excluded(rel, rules if rules is not None else dockerignore_rules())


def _module_candidates(module: str) -> list[str]:
    stem = module.replace(".", "/")
    found = []
    for candidate in (f"{stem}.py", f"{stem}/__init__.py"):
        if (ROOT / candidate).is_file():
            found.append(candidate)
    return found


def resolve_import(current: str, node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        found: list[str] = []
        for alias in node.names:
            if alias.name == "forex_bot" or alias.name.startswith("forex_bot."):
                found.extend(_module_candidates(alias.name) or [f"MISSING:{alias.name}"])
        return found
    if not isinstance(node, ast.ImportFrom):
        return []
    package = list(Path(current).parts[:-1])
    if node.level:
        if node.level - 1 > len(package):
            return [f"MISSING:relative:{current}:{node.lineno}"]
        base = package[: len(package) - (node.level - 1)]
    else:
        base = []
    module_parts = (node.module or "").split(".") if node.module else []
    full = [*base, *module_parts]
    found = []
    if full and full[0] == "forex_bot":
        module = ".".join(full)
        found.extend(_module_candidates(module) or [f"MISSING:{module}"])
    if node.level and not node.module:
        for alias in node.names:
            if alias.name == "*":
                continue
            module = ".".join([*base, alias.name])
            if module.startswith("forex_bot"):
                candidates = _module_candidates(module)
                if candidates:
                    found.extend(candidates)
    return found


def production_closure(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    seen: set[str] = set()
    queue = list(ENTRY_MODULES)
    missing: list[str] = []
    dynamic: list[str] = []
    file_reads: list[str] = []
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        path = base / rel
        if not path.is_file():
            missing.append(rel)
            continue
        seen.add(rel)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for dest in resolve_import(rel, node):
                    if dest.startswith("MISSING:"):
                        missing.append(f"{rel}:{dest}")
                    elif dest not in seen:
                        queue.append(dest)
            if isinstance(node, ast.Call):
                label = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if label in {"import_module", "__import__"}:
                    dynamic.append(f"{rel}:{node.lineno}:{label}")
                if label in {"open", "read_text", "read_bytes", "files"}:
                    file_reads.append(f"{rel}:{node.lineno}:{label}")
    text_markers = []
    for rel in sorted(seen):
        text = (base / rel).read_text(encoding="utf-8")
        hits = [name for name in ("importlib", "__import__", "pkgutil", "subprocess") if name in text]
        if hits:
            text_markers.append({"path": rel, "markers": hits})
    return {
        "entry_modules": list(ENTRY_MODULES),
        "modules": sorted(seen),
        "missing": missing,
        "dynamic_calls": dynamic,
        "file_read_calls": file_reads,
        "text_markers": text_markers,
        "uvicorn_string_target": "forex_bot.app:app",
    }


def verify_dockerfile(
    dockerfile: str,
    *,
    paths: list[str],
    root: Path,
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings: list[str] = []
    text = dockerfile.replace("\r\n", "\n")
    if FROM_LINE not in text:
        findings.append("base_image_changed")
    if WORKDIR_LINE not in text:
        findings.append("workdir_changed")
    if PIP_COMMAND not in text:
        findings.append("dependency_install_changed")
    if text.count(ENTRYPOINT) != 1:
        findings.append("entrypoint_changed")
    if "COPY . ." in text or "COPY . ." in text.replace("  ", " "):
        findings.append("unrestricted_context_copy")
    try:
        copies = parse_copies(text)
    except ValueError as exc:
        return {"ok": False, "findings": [*findings, str(exc)], "copies": []}
    expected = application_copy_paths(paths)
    sources = [source for source, _dest in copies]
    if sources.count("main.py") != 1:
        findings.append("main_py_not_copied_once")
    if any(source in {"forex_bot", "forex_bot/", "./forex_bot", "./forex_bot/"} for source, _dest in copies):
        findings.append("broad_package_copy")
    if any("*" in source or "*" in dest for source, dest in copies):
        findings.append("wildcard_copy")
    unsafe_names = {".env", "credentials.json"}
    if any(
        source.startswith(("/", "../")) or "/../" in source or source.split("/")[0] in unsafe_names
        for source, _dest in copies
    ):
        findings.append("unsafe_source")
    destinations: dict[str, str] = {}
    for source, dest in copies:
        destination = _destination(source, dest)
        if _escapes_app(destination) or ".." in Path(dest).parts:
            findings.append(f"destination_escapes_app:{destination}")
        if destination in destinations:
            findings.append(f"duplicate_destination:{destination}")
        destinations[destination] = source
        if source in {"Dockerfile", ".dockerignore"}:
            findings.append(f"policy_file_copied:{source}")
        sensitive = Path(source).name.lower()
        if sensitive in {".env", "credentials.json", "id_rsa"} or sensitive.endswith((".pem", ".key")):
            findings.append(f"credential_source:{source}")
        candidate = (root / source)
        if candidate.is_symlink() or (candidate.exists() and is_reparse_point(candidate)):
            findings.append(f"symlink_or_reparse:{source}")
        try:
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root.resolve()):
                findings.append(f"source_escapes_repo:{source}")
            elif "data" in resolved.relative_to(root.resolve()).parts and source.startswith("data"):
                findings.append(f"source_in_data:{source}")
        except (OSError, ValueError):
            findings.append(f"source_unreadable:{source}")
        if rules is not None and source_excluded(source, rules):
            findings.append(f"dockerignore_excluded:{source}")
    missing = sorted(set(expected) - set(sources))
    extra = sorted(set(sources) - set(expected))
    if missing:
        findings.append("missing_allowlist_entries")
    if extra:
        findings.append("unexpected_copy_sources")
    return {
        "ok": not findings and not missing and not extra,
        "findings": findings,
        "missing": missing,
        "extra": extra,
        "copy_count": len(copies),
        "main_py_copies": sources.count("main.py"),
        "destinations": destinations,
    }
