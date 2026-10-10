"""Stage G.10 snapshot checks. These tests do not rewrite the official archive."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from forex_bot.live_safety import (
    AUTH_ALLOWED,
    AUTH_BLOCKED,
    KNOWN_STRATEGY_NAMES,
    REASON_DEFAULT_DENY,
    REASON_PERSISTED_ALLOWED_IGNORED,
    initialise_fail_closed,
    live_order_auth_reason,
    live_order_auth_state,
    reset_live_safety_for_tests,
    state_path,
)
from forex_bot.research.adaptive_ensemble.g10_snapshot import (
    G7_ARCHIVE,
    ROOT,
    SNAPSHOT_ID,
    build_manifest,
    write_candidate,
)
from forex_bot.research.adaptive_ensemble.g10_verify import verify_archive
from forex_bot.strategy_meta import strategies

G10 = ROOT / "data" / "research" / "adaptive_ensemble" / "g10"
OFFICIAL_TAR = G10 / "source_snapshot.tar"
OFFICIAL_MANIFEST = G10 / "source_manifest.json"
G7_TAR = ROOT / "data" / "research" / "adaptive_ensemble" / "g7" / "source_snapshot.tar"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _member(name: str, data: bytes, *, mtime: int = 0, link: str = "") -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    info.mtime = mtime
    info.mode = 0o644
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.type = tarfile.SYMTYPE if link == "sym" else tarfile.LNKTYPE if link == "hard" else tarfile.REGTYPE
    if link:
        info.linkname = "other"
        info.size = 0
    return info


def _tar(members: list[tuple[tarfile.TarInfo, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for info, data in members:
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _manifest(files: list[dict[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {
        "archive_format": "ustar",
        "files": files,
        "g4_package_hash": "x",
        "g4_policy_hash": "x",
        "payload_bytes": sum(int(row["size"]) for row in files),
        "protocol_hash": "x",
        "provenance_version": "market_provenance_v2",
        "snapshot_id": SNAPSHOT_ID,
        "snapshot_tool": "g10_test_fixture",
        "source_file_count": len(files),
    }
    body = {key: value for key, value in payload.items()}
    payload["manifest_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def _write_pair(directory: Path, blob: bytes, manifest: dict[str, object]) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    tar_path = directory / "sample.tar"
    manifest_path = directory / "sample.json"
    tar_path.write_bytes(blob)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return tar_path, manifest_path


def test_two_temporary_candidates_are_identical(tmp_path: Path):
    first = write_candidate(tmp_path / "a" / "source_snapshot.tar", tmp_path / "a" / "source_manifest.json")
    second = write_candidate(tmp_path / "b" / "source_snapshot.tar", tmp_path / "b" / "source_manifest.json")
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert (tmp_path / "a" / "source_snapshot.tar").read_bytes() == (tmp_path / "b" / "source_snapshot.tar").read_bytes()
    assert first["snapshot_id"] == SNAPSHOT_ID
    assert all(not row["path"].startswith("data/") for row in first["files"])


def test_official_archive_is_independently_verified_and_not_rewritten():
    before = OFFICIAL_TAR.read_bytes()
    recorded = json.loads((G10 / "snapshot_verification.json").read_text(encoding="utf-8"))
    result = verify_archive(OFFICIAL_TAR, OFFICIAL_MANIFEST, expected_archive_sha256=recorded["archive_sha256"])
    assert result["ok"] is True
    assert result["archive_sha256"] == recorded["archive_sha256"]
    assert result["manifest_sha256"] == recorded["manifest_sha256"]
    assert OFFICIAL_TAR.read_bytes() == before
    fresh = build_manifest()
    assert fresh["manifest_sha256"] == recorded["manifest_sha256"]


def test_g7_archive_remains_frozen():
    assert _sha(G7_TAR) == G7_ARCHIVE


def test_snapshot_contains_candle_repairs():
    with tarfile.open(OFFICIAL_TAR, "r:") as archive:
        handle = archive.extractfile("forex_bot/bot_loop.py")
        assert handle is not None
        text = handle.read().decode("utf-8")
    assert "_contain_candle_exception" in text
    assert "class CycleIntegrityError" in text
    assert "except AssertionError:" in text
    assert "MANAGEMENT_CONTINUED_WITHOUT_CANDLES" in text
    assert "if raw is None or raw.empty:" not in text


def test_adversarial_archive_mutations_are_rejected(tmp_path: Path):
    good = b"alpha\n"
    other = b"beta\n"
    files = [
        {"path": "a.txt", "sha256": hashlib.sha256(good).hexdigest(), "size": len(good)},
        {"path": "b.txt", "sha256": hashlib.sha256(other).hexdigest(), "size": len(other)},
    ]
    manifest = _manifest(files)
    blob = _tar([(_member("a.txt", good), good), (_member("b.txt", other), other)])
    tar_path, manifest_path = _write_pair(tmp_path / "good", blob, manifest)
    assert verify_archive(tar_path, manifest_path)["ok"] is True

    changed = bytearray(good)
    changed[0] = ord("z")
    bad_blob = _tar([(_member("a.txt", bytes(changed)), bytes(changed)), (_member("b.txt", other), other)])
    bad_tar, _ = _write_pair(tmp_path / "byte", bad_blob, manifest)
    assert verify_archive(bad_tar, manifest_path)["reason"] == "file_hash"

    removed = _tar([(_member("a.txt", good), good)])
    removed_tar, _ = _write_pair(tmp_path / "removed", removed, manifest)
    assert verify_archive(removed_tar, manifest_path)["reason"] == "missing_file"

    extra = b"c\n"
    added = _tar(
        [
            (_member("a.txt", good), good),
            (_member("b.txt", other), other),
            (_member("c.txt", extra), extra),
        ]
    )
    added_tar, _ = _write_pair(tmp_path / "added", added, manifest)
    assert verify_archive(added_tar, manifest_path)["reason"] == "unexpected_file"

    duplicate = _tar([(_member("a.txt", good), good), (_member("a.txt", good), good)])
    one = _manifest([{"path": "a.txt", "sha256": hashlib.sha256(good).hexdigest(), "size": len(good)}])
    dup_tar, dup_manifest = _write_pair(tmp_path / "dup", duplicate, one)
    assert verify_archive(dup_tar, dup_manifest)["reason"] == "duplicate_path"

    traversal = _tar([(_member("../a.txt", good), good)])
    trav_manifest = _manifest([{"path": "a.txt", "sha256": hashlib.sha256(good).hexdigest(), "size": len(good)}])
    trav_tar, trav_man = _write_pair(tmp_path / "trav", traversal, trav_manifest)
    assert verify_archive(trav_tar, trav_man)["reason"] == "unsafe_path"

    absolute = _tar([(_member("/tmp/a.txt", good), good)])
    abs_tar, abs_man = _write_pair(tmp_path / "abs", absolute, trav_manifest)
    assert verify_archive(abs_tar, abs_man)["reason"] == "unsafe_path"

    forged = dict(manifest)
    forged_files = [dict(row) for row in files]
    forged_files[0]["sha256"] = "0" * 64
    forged = _manifest(forged_files)
    forged_tar, forged_man = _write_pair(tmp_path / "hash", blob, forged)
    assert verify_archive(forged_tar, forged_man)["reason"] == "file_hash"

    broken = dict(manifest)
    broken["manifest_sha256"] = "0" * 64
    broken_tar, broken_man = _write_pair(tmp_path / "man", blob, broken)
    assert verify_archive(broken_tar, broken_man)["reason"] == "manifest_hash"

    assert verify_archive(tar_path, manifest_path, expected_archive_sha256="0" * 64)["reason"] == "archive_hash"

    symlink = _tar([(_member("a.txt", b"", link="sym"), b"")])
    sym_tar, sym_man = _write_pair(tmp_path / "sym", symlink, one)
    assert verify_archive(sym_tar, sym_man)["reason"] == "unsupported_member"

    hard = _tar([(_member("a.txt", b"", link="hard"), b"")])
    hard_tar, hard_man = _write_pair(tmp_path / "hard", hard, one)
    assert verify_archive(hard_tar, hard_man)["reason"] == "unsupported_member"

    stale = _tar([(_member("a.txt", good, mtime=5), good)])
    stale_tar, stale_man = _write_pair(tmp_path / "meta", stale, one)
    assert verify_archive(stale_tar, stale_man)["reason"] == "metadata"

    reversed_tar = _tar([(_member("b.txt", other), other), (_member("a.txt", good), good)])
    rev_tar, rev_man = _write_pair(tmp_path / "order", reversed_tar, manifest)
    assert verify_archive(rev_tar, rev_man)["reason"] == "member_order"


def test_missing_safety_state_and_persisted_allowed_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LIVE_SAFETY_STATE_PATH", str(tmp_path / "absent.json"))
    reset_live_safety_for_tests()
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert live_order_auth_reason() == REASON_DEFAULT_DENY
    assert all(strategies[name].active is False for name in KNOWN_STRATEGY_NAMES)
    doc = json.loads(state_path().read_text(encoding="utf-8"))
    doc["live_order_authorisation"]["state"] = AUTH_ALLOWED
    state_path().write_text(json.dumps(doc), encoding="utf-8")
    reset_live_safety_for_tests()
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert live_order_auth_reason() == REASON_PERSISTED_ALLOWED_IGNORED
    assert all(strategies[name].active is False for name in KNOWN_STRATEGY_NAMES)


def test_allowlist_retains_safety_modules_and_drops_research():
    allow = json.loads((G10 / "production_allowlist.json").read_text(encoding="utf-8"))
    included = {row["path"] for row in allow["files"]}
    for required in (
        "forex_bot/live_safety.py",
        "forex_bot/market_provenance.py",
        "forex_bot/bot_loop.py",
        "forex_bot/oanda_exec.py",
        "forex_bot/live_manage.py",
    ):
        assert required in included
    assert all(not path.startswith("forex_bot/research/") for path in included)
    assert allow["image_build_authorised"] is False
    assert allow["dockerfile_still_copies_entire_package"] is True
