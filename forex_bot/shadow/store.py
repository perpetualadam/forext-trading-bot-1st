"""Simulated-only JSONL/state. Never writes live trades, exec_orders, or safety JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def _jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


class ShadowStore:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        readme = self.directory / "README_SIMULATED.txt"
        if not readme.exists():
            readme.write_text(
                "SIMULATED_SHADOW_NOT_BROKER\n"
                "These files are hypothetical. They are not OANDA fills or live P&L.\n",
                encoding="utf-8",
            )
        self.events_path = self.directory / "shadow_events.jsonl"
        self.state_path = self.directory / "shadow_state.json"

    def append_event(self, payload: dict[str, Any]) -> None:
        row = {"simulated": True, "label": "SIMULATED_SHADOW_NOT_BROKER", **_jsonable(payload)}
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    def write_state(self, payload: dict[str, Any]) -> None:
        blob = {"simulated": True, "label": "SIMULATED_SHADOW_NOT_BROKER", **_jsonable(payload)}
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(blob, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.state_path)

    def read_state(self) -> dict[str, Any] | None:
        if not self.state_path.is_file():
            return None
        try:
            blob = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return blob if isinstance(blob, dict) else None
