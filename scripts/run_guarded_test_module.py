"""Run one stage's complete test module behind its pre-import network barrier."""

from __future__ import annotations

import os
from pathlib import Path
import re
import socket
import sys

root = Path(__file__).resolve().parents[1]
target = (root / sys.argv[1]).resolve()
if target.parent != root / "tests" or not target.name.startswith("test_r"):
    raise SystemExit("Refusing a non-stage test target")
stage = re.match(r"test_(r\d+)_", target.name).group(1).upper()
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ["PYTEST_ADDOPTS"] = ""
os.environ["PYTHON_DOTENV_DISABLED"] = "1"


class BlockedSocket(socket.socket):
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError(f"{stage}_NETWORK_BLOCKED")


def blocked_dns(*_args, **_kwargs):
    raise RuntimeError(f"{stage}_DNS_BLOCKED")


socket.socket = BlockedSocket
socket.getaddrinfo = blocked_dns
socket.gethostbyname = blocked_dns
socket.create_connection = blocked_dns
sys.path.insert(0, str(root))

import pytest  # noqa: E402: the barrier must precede test/application imports

raise SystemExit(pytest.main(["--noconftest", "-p", "no:cacheprovider", "-q", str(target)]))
