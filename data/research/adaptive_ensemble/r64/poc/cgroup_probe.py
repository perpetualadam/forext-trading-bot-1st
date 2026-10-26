"""Read-only cgroup v2 probe. A failed mkdir is removed when it was created.

This module does not write cgroup.kill and does not change controllers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

CGROUP_DELEGATION_UNAVAILABLE = "CGROUP_DELEGATION_UNAVAILABLE"
CGROUP_V2_DELEGATED = "CGROUP_V2_DELEGATED"


def probe_host() -> dict[str, object]:
    if not sys.platform.startswith("linux"):
        return {
            "operating_system": sys.platform,
            "status": CGROUP_DELEGATION_UNAVAILABLE,
            "delegated": False,
            "reason": "UNSUPPORTED_PLATFORM",
            "evidence": "REAL",
            "kernel_containment": False,
        }
    mount = _mount_options()
    version = _os_release()
    relative = _self_cgroup()
    base = Path("/sys/fs/cgroup") / relative.lstrip("/")
    controllers = _read(Path("/sys/fs/cgroup/cgroup.controllers"))
    subtree = _read(Path("/sys/fs/cgroup/cgroup.subtree_control"))
    caps = _caps()
    target = base / f"r64-probe-{os.getpid()}"
    errno = 0
    created = False
    try:
        target.mkdir()
        created = True
    except OSError as exc:
        errno = exc.errno or 0
    if created:
        try:
            target.rmdir()
        except OSError:
            pass
    delegated = created and (base / "cgroup.kill").is_file() and (base / "cgroup.procs").is_file()
    return {
        "operating_system": version.get("PRETTY_NAME", "Linux"),
        "kernel": os.uname().release,
        "python": sys.version.split()[0],
        "status": CGROUP_V2_DELEGATED if delegated else CGROUP_DELEGATION_UNAVAILABLE,
        "delegated": delegated,
        "reason": "PRIVATE_CHILD_CREATED" if delegated else f"MKDIR_ERRNO_{errno}",
        "evidence": "REAL",
        "kernel_containment": False,
        "mount": mount,
        "self_cgroup": relative,
        "base": str(base),
        "base_writable": os.access(base, os.W_OK),
        "procs_present": (base / "cgroup.procs").is_file(),
        "kill_present": (base / "cgroup.kill").is_file(),
        "root_kill_present": Path("/sys/fs/cgroup/cgroup.kill").is_file(),
        "controllers": controllers,
        "subtree_control": subtree,
        "user_service": Path("/sys/fs/cgroup/user.slice/user-1000.slice").is_dir(),
        "cap_eff": caps.get("CapEff", ""),
        "no_new_privs": caps.get("NoNewPrivs", ""),
        "cgroup_namespace": _namespace("cgroup"),
        "pid_namespace": _namespace("pid"),
        "user_namespace": _namespace("user"),
    }


def current_cgroup_path() -> Path | None:
    if not sys.platform.startswith("linux"):
        return None
    relative = _self_cgroup()
    return Path("/sys/fs/cgroup") / relative.lstrip("/")


def _self_cgroup() -> str:
    text = Path("/proc/self/cgroup").read_text(encoding="utf-8")
    for line in text.splitlines():
        parts = line.split(":")
        if parts and parts[0] == "0":
            return parts[-1]
    return ""


def _mount_options() -> str:
    try:
        for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
            if " /sys/fs/cgroup " in f" {line} " or line.split()[-2:] == ["/sys/fs/cgroup", "cgroup2"]:
                if "/sys/fs/cgroup" in line and "cgroup2" in line:
                    return line
    except OSError:
        return ""
    return ""


def _os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    except OSError:
        pass
    return values


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _caps() -> dict[str, str]:
    found: dict[str, str] = {}
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith(("CapEff:", "NoNewPrivs:")):
                key, value = line.split(":", 1)
                found[key] = value.strip()
    except OSError:
        pass
    return found


def _namespace(name: str) -> str:
    link = Path("/proc/self/ns") / name
    try:
        return os.readlink(link)
    except OSError:
        return ""
