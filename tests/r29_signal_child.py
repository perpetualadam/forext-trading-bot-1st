"""Print one scalp signal for a local frame. No network and no dotenv."""

from __future__ import annotations

import json
import socket
import sys
import types
from pathlib import Path

import pandas as pd


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R29_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R29_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = dotenv
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forex_bot.shadow.signals import prepare_frame, signal_from_indicators  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

frame = pd.read_json(Path(sys.argv[1]))
ready, status = prepare_frame(frame, 50)
if status != "ok" or ready is None:
    print(json.dumps({"direction": None, "reason": status, "active": False}))
else:
    direction, reason = signal_from_indicators("scalp", ready)
    print(
        json.dumps(
            {
                "direction": direction,
                "reason": reason,
                "active": bool(strategies["scalp"].active),
            }
        )
    )
