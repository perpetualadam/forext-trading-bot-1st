"""Independent Stage G.12.1 archive reader.

This module does not import the Stage G.12 parser and does not call Docker.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any

EXPECTED_IMAGE = "sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25"
CLEANUP_TOKEN = "OPERATOR_APPROVED_ARCHIVE_DELETE"
WANTED = (
    "forex_bot/live_safety.py",
    "forex_bot/app.py",
    "forex_bot/database.py",
    "forex_bot/bot_loop.py",
    "forex_bot/oanda_exec.py",
    "forex_bot/oanda_client.py",
    "forex_bot/live_manage.py",
    "forex_bot/decision_skip_log.py",
    "forex_bot/market_provenance.py",
    "main.py",
)


class ForensicIntegrityError(RuntimeError):
    """The archive or a layer failed an independent check."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def assert_cleanup_approved(approval: str | None) -> None:
    if approval != CLEANUP_TOKEN:
        raise PermissionError("CLEANUP_APPROVAL_REQUIRED")


def _unsafe_name(name: str) -> bool:
    if name.startswith(("/", "\\")) or (len(name) > 1 and name[1] == ":"):
        return True
    return any(part == ".." for part in name.replace("\\", "/").split("/"))


def _app_path(name: str) -> str:
    path = name.replace("\\", "/").lstrip("./")
    if path.startswith("app/"):
        return path[4:]
    return path


def _call_label(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        base = func.value
        if isinstance(base, ast.Name):
            return base.id + "." + func.attr
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def ordered_calls(tree: ast.AST) -> list[str]:
    found: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            found.append(_call_label(node))
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def function_calls(source: str, name: str) -> list[str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ordered_calls(node)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return ordered_calls(node)
    return []


def _read_member(archive: tarfile.TarFile, name: str) -> bytes:
    try:
        handle = archive.extractfile(name)
    except KeyError as exc:
        raise ForensicIntegrityError("missing member") from exc
    if handle is None:
        raise ForensicIntegrityError("missing member")
    return handle.read()


def verify_save(path: Path) -> dict[str, Any]:
    """Re-open an OCI/docker image save and rebuild the application tree."""
    try:
        with tarfile.open(path, "r:") as archive:
            try:
                manifest_doc = json.loads(_read_member(archive, "manifest.json").decode("utf-8"))
            except (KeyError, json.JSONDecodeError, UnicodeError) as exc:
                raise ForensicIntegrityError("manifest") from exc
            if not isinstance(manifest_doc, list) or len(manifest_doc) != 1:
                raise ForensicIntegrityError("manifest")
            entry = manifest_doc[0]
            layers = entry.get("Layers")
            config_name = entry.get("Config")
            if not isinstance(layers, list) or not layers or not isinstance(config_name, str):
                raise ForensicIntegrityError("manifest")
            if len(layers) != len(set(layers)):
                raise ForensicIntegrityError("duplicate layer reference")
            config_bytes = _read_member(archive, config_name)
            config_digest = sha256_bytes(config_bytes)
            if config_digest != config_name.rsplit("/", 1)[-1]:
                raise ForensicIntegrityError("config digest")
            config = json.loads(config_bytes)
            env_names = sorted(
                {
                    item.split("=", 1)[0]
                    for item in config.get("config", {}).get("Env", [])
                    if isinstance(item, str) and "=" in item
                }
            )
            diff_ids = [item.split(":", 1)[1] for item in config["rootfs"]["diff_ids"]]
            if len(diff_ids) != len(layers):
                raise ForensicIntegrityError("layer count")
            index_doc = json.loads(_read_member(archive, "index.json").decode("utf-8"))
            image_id = "sha256:" + str(index_doc["manifests"][0]["digest"]).split(":", 1)[-1]
            layer_rows: list[dict[str, Any]] = []
            tree: dict[str, bytes] = {}
            replaced: list[str] = []
            hidden: list[dict[str, str]] = []
            sensitive: list[dict[str, str]] = []
            app_links = 0
            for index, layer_name in enumerate(layers):
                blob = _read_member(archive, str(layer_name))
                blob_digest = sha256_bytes(blob)
                expected_blob = str(layer_name).rsplit("/", 1)[-1]
                if blob_digest != expected_blob:
                    raise ForensicIntegrityError("blob digest")
                try:
                    payload = gzip.decompress(blob) if blob[:2] == b"\x1f\x8b" else blob
                except gzip.BadGzipFile as exc:
                    raise ForensicIntegrityError("decompress") from exc
                diff_id = sha256_bytes(payload)
                if diff_id != diff_ids[index]:
                    raise ForensicIntegrityError("diff id")
                layer_rows.append(
                    {
                        "index": index,
                        "reference": str(layer_name),
                        "expected_digest": expected_blob,
                        "actual_digest": blob_digest,
                        "expected_diff_id": diff_ids[index],
                        "actual_diff_id": diff_id,
                        "compressed_bytes": len(blob),
                        "uncompressed_bytes": len(payload),
                        "verified": True,
                    }
                )
                with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as layer:
                    seen: set[str] = set()
                    opaque: set[str] = set()
                    whiteouts: set[str] = set()
                    files: list[tuple[str, bytes]] = []
                    for info in layer.getmembers():
                        if _unsafe_name(info.name):
                            raise ForensicIntegrityError("unsafe path")
                        if info.name in seen:
                            raise ForensicIntegrityError("duplicate member")
                        seen.add(info.name)
                        lowered = info.name.replace("\\", "/").lower()
                        if lowered.endswith((".env", ".pem", ".key")) or lowered.rsplit("/", 1)[-1] in {
                            "id_rsa",
                            "credentials.json",
                        }:
                            sensitive.append(
                                {
                                    "path": lowered,
                                    "classification": "public_ca_bundle"
                                    if "/ssl/certs/" in lowered
                                    or lowered.endswith(("cacert.pem", "/ssl/cert.pem"))
                                    else "review",
                                    "content_stored": "false",
                                }
                            )
                        if info.issym() or info.islnk():
                            if _app_path(info.name).startswith("forex_bot/") or _app_path(info.name) in WANTED:
                                app_links += 1
                                raise ForensicIntegrityError("application link")
                            continue
                        if info.isdev() or info.isfifo():
                            if _app_path(info.name).startswith("forex_bot/"):
                                raise ForensicIntegrityError("special file")
                            continue
                        if not info.isfile():
                            continue
                        raw_name = info.name.replace("\\", "/").rstrip("/")
                        base = raw_name.rsplit("/", 1)[-1]
                        parent = _app_path(raw_name.rsplit("/", 1)[0]) if "/" in raw_name else ""
                        if base == ".wh..wh..opq":
                            opaque.add(parent)
                            continue
                        if base.startswith(".wh."):
                            target_name = base[4:]
                            whiteouts.add(target_name if not parent else parent + "/" + target_name)
                            continue
                        rel = _app_path(raw_name)
                        if rel in WANTED or rel.startswith("forex_bot/"):
                            handle = layer.extractfile(info)
                            files.append((rel, b"" if handle is None else handle.read()))
                    for directory in opaque:
                        prefix = directory + "/" if directory else ""
                        for item in [key for key in tree if key == directory or key.startswith(prefix)]:
                            hidden.append({"path": item, "action": "opaque", "layer": str(index)})
                            tree.pop(item, None)
                    for wiped in whiteouts:
                        prefix = wiped + "/"
                        removed = [key for key in tree if key == wiped or key.startswith(prefix)]
                        for item in removed:
                            hidden.append({"path": item, "action": "whiteout", "layer": str(index)})
                            tree.pop(item, None)
                    for rel, data in files:
                        if rel in tree:
                            replaced.append(rel)
                        tree[rel] = data
            return {
                "image_id": image_id,
                "config_digest": config_digest,
                "config_env_names": env_names,
                "layer_count": len(layer_rows),
                "layers": layer_rows,
                "files": {key: sha256_bytes(value) for key, value in tree.items() if key in WANTED or key == "main.py"},
                "bodies": {key: tree[key] for key in WANTED if key in tree},
                "application_paths": sorted(path for path in tree if path.startswith("forex_bot/") or path == "main.py"),
                "replaced_application_paths": sorted(set(replaced)),
                "hidden_application_paths": hidden,
                "application_links": app_links,
                "sensitive_names": sensitive,
                "provenance_mentions": sorted(
                    path
                    for path, data in tree.items()
                    if path.endswith(".py") and b"market_provenance" in data
                ),
            }
    except ForensicIntegrityError:
        raise
    except (tarfile.TarError, OSError) as exc:
        raise ForensicIntegrityError("archive") from exc



def pin_hash(archive: Path, name: str) -> str | None:
    with tarfile.open(archive, "r:") as handle:
        try:
            member = handle.extractfile(name)
        except KeyError:
            return None
        if member is None:
            return None
        return sha256_bytes(member.read())


def mutation_sites(source: str) -> list[dict[str, str]]:
    tree = ast.parse(source)
    rows: list[dict[str, str]] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        labels = ordered_calls(node)
        for label in labels:
            if label in {
                "oanda_orders.OrderCreate",
                "oanda_positions.PositionClose",
                "oanda_orders.OrderCancel",
                "oanda_orders.OrderReplace",
                "oanda_trades.TradeClose",
            }:
                rows.append({"function": node.name, "call": label})
    return rows


def _string_constants(node: ast.AST) -> set[str]:
    return {item.value for item in ast.walk(node) if isinstance(item, ast.Constant) and isinstance(item.value, str)}


def _imports(source: str, module_name: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module and module_name in node.module.split("."):
            return True
        if isinstance(node, ast.Import) and any(module_name in alias.name.split(".") for alias in node.names):
            return True
    return False


def _function(source: str, name: str) -> ast.AST | None:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def inspect_controls(bodies: dict[str, bytes]) -> dict[str, Any]:
    """Static call-path notes. This does not execute the image and does not prove runtime state."""
    text = {key: value.decode("utf-8") for key, value in bodies.items()}
    app = text["forex_bot/app.py"]
    safety = text["forex_bot/live_safety.py"]
    bot = text["forex_bot/bot_loop.py"]
    execution = text["forex_bot/oanda_exec.py"]
    client = text["forex_bot/oanda_client.py"]
    database = text["forex_bot/database.py"]
    safety_tree = ast.parse(safety)
    constants = {
        node.targets[0].id: node.value.value
        for node in safety_tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    init = _function(safety, "initialise_fail_closed")
    init_calls = ordered_calls(init) if init is not None else []
    init_names = {node.id for node in ast.walk(init) if isinstance(node, ast.Name)} if init is not None else set()
    init_strings = {constants[name] for name in init_names if name in constants}
    open_calls = function_calls(execution, "_place_market_order_open_sync")
    close_calls = function_calls(execution, "_place_market_order_sync")
    sites = mutation_sites(execution)
    early_returns: list[dict[str, Any]] = []
    for node in ast.walk(ast.parse(bot)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.If):
                continue
            test = ast.dump(child.test)
            returns = any(isinstance(item, ast.Return) for item in child.body)
            if returns and "empty" in test and "raw" in test:
                later_calls = [
                    _call_label(item)
                    for item in ast.walk(node)
                    if isinstance(item, ast.Call) and getattr(item, "lineno", 0) > child.lineno
                ]
                early_returns.append(
                    {
                        "function": node.name,
                        "returns_on_empty_raw": True,
                        "later_manage_or_position_calls": [
                            label for label in later_calls if "manage" in label.lower() or "Position" in label
                        ],
                    }
                )
    return {
        "startup_calls_initialise_fail_closed": "initialise_fail_closed" in ordered_calls(ast.parse(app)),
        "missing_state_blocked_constant": "default_deny_no_durable_state" in init_strings,
        "persisted_allowed_ignored_constant": "persisted_allowed_ignored_until_operator_action" in init_strings,
        "initialise_sets_blocked": "_set_effective_blocked" in init_calls,
        "initialise_persists_state": "_persist_unlocked" in init_calls,
        "open_gate_before_order_create": (
            "assert_new_live_exposure_allowed" in open_calls
            and "oanda_orders.OrderCreate" in open_calls
            and open_calls.index("assert_new_live_exposure_allowed") < open_calls.index("oanda_orders.OrderCreate")
        ),
        "mutation_calls": sites,
        "order_cancel_present": any(row["call"] == "oanda_orders.OrderCancel" for row in sites),
        "order_replace_present": any(row["call"] == "oanda_orders.OrderReplace" for row in sites),
        "trade_close_present": any(row["call"] == "oanda_trades.TradeClose" for row in sites),
        "require_order_quote_called": "require_order_quote" in ordered_calls(ast.parse(execution)),
        "protective_close_withheld_constant": "protective close withheld" in _string_constants(ast.parse(execution)),
        "client_imports_provenance": _imports(client, "market_provenance"),
        "bot_imports_provenance": _imports(bot, "market_provenance"),
        "contain_candle_exception_defined": _function(bot, "_contain_candle_exception") is not None,
        "cycle_integrity_error_defined": any(
            isinstance(node, ast.ClassDef) and node.name == "CycleIntegrityError" for node in ast.parse(bot).body
        ),
        "empty_candle_return_before_later_manage_calls": early_returns,
        "database_executes_ddl": "CREATE TABLE IF NOT EXISTS" in database,
        "database_called_from_app": "get_connection" in ordered_calls(ast.parse(app)),
        "close_calls_authorisation": "assert_new_live_exposure_allowed" in close_calls,
        "static_inspection_proves_runtime": False,
    }


def redact_text(text: str) -> dict[str, bool]:
    private = (b"BEGIN " + b"PRIVATE KEY").decode() in text or (b"BEGIN RSA " + b"PRIVATE KEY").decode() in text
    assigned = False
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and value.strip() and key.strip() in {"OANDA_ACCESS_TOKEN", "POSTGRES_PASSWORD", "POSTGRES_PASS"}:
            assigned = True
    return {"private_key_banner": private, "credential_assignment": assigned, "value_stored": False}


def mutation_inventory(source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    watched = {
        "oanda_orders.OrderCreate",
        "oanda_positions.PositionClose",
        "oanda_orders.OrderCancel",
        "oanda_orders.OrderReplace",
        "oanda_trades.TradeClose",
    }
    for node in ast.parse(source).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        labels = ordered_calls(node)
        strings = _string_constants(node)
        keywords: set[str] = set()
        for call in ast.walk(node):
            if isinstance(call, ast.Call):
                keywords.update(item.arg for item in call.keywords if item.arg)
        for label in labels:
            if label not in watched:
                continue
            method = "unseen"
            if "POST" in strings:
                method = "POST"
            elif "PUT" in strings:
                method = "PUT"
            rows.append(
                {
                    "module": "forex_bot/oanda_exec.py",
                    "function": node.name,
                    "broker_operation": label,
                    "http_method_literal": method,
                    "endpoint_literals": sorted(item for item in strings if item.startswith("/v3/")),
                    "exposure": "increasing" if label.endswith("OrderCreate") else "reducing",
                    "authorisation_before_call": (
                        "assert_new_live_exposure_allowed" in labels
                        and labels.index("assert_new_live_exposure_allowed") < labels.index(label)
                    ),
                    "timeout_keyword_present": "timeout" in keywords,
                    "exception_handler_present": any(isinstance(item, ast.ExceptHandler) for item in ast.walk(node)),
                    "audit_call_present": any("log" in item.lower() or "audit" in item.lower() for item in labels),
                }
            )
    return rows


def stage_classification(*, archive_ok: bool, layers_ok: bool, files_ok: bool) -> str:
    if not archive_ok:
        return "FORENSIC_ARCHIVE_INTEGRITY_FAILED"
    if not layers_ok:
        return "FORENSIC_LAYER_INTEGRITY_FAILED"
    if files_ok:
        return "INDEPENDENT_FORENSICS_VERIFIED_CLEANUP_APPROVAL_REQUIRED"
    return "INDEPENDENT_FORENSICS_PARTIAL_CLEANUP_BLOCKED"
