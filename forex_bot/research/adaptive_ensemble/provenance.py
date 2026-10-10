"""Dataset provenance, overlap detection, and contamination labels."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

STAGE_EG_END = datetime(2026, 8, 31, 23, 50, tzinfo=timezone.utc)
STAGE_EG_START = datetime(2025, 9, 1, 0, 0, tzinfo=timezone.utc)

PREVIOUSLY_EXAMINED = "PREVIOUSLY_EXAMINED"
NEWLY_ACQUIRED_BUT_EXPOSED = "NEWLY_ACQUIRED_BUT_EXPOSED"
POTENTIALLY_INDEPENDENT = "POTENTIALLY_INDEPENDENT"
INDEPENDENCE_NOT_ESTABLISHED = "INDEPENDENCE_NOT_ESTABLISHED"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify_period(start: datetime | None, end: datetime | None, *, exposed: bool) -> str:
    if start is None or end is None:
        return INDEPENDENCE_NOT_ESTABLISHED
    if end <= STAGE_EG_END and start >= STAGE_EG_START:
        return PREVIOUSLY_EXAMINED
    if start <= STAGE_EG_END <= end:
        return PREVIOUSLY_EXAMINED if not (end > STAGE_EG_END) else (
            NEWLY_ACQUIRED_BUT_EXPOSED if exposed else INDEPENDENCE_NOT_ESTABLISHED
        )
    if start > STAGE_EG_END:
        if exposed:
            return NEWLY_ACQUIRED_BUT_EXPOSED
        return POTENTIALLY_INDEPENDENT
    return INDEPENDENCE_NOT_ESTABLISHED


def overlap_with_stage_eg(times: pd.Series) -> dict[str, Any]:
    t = pd.to_datetime(times, utc=True, errors="coerce").dropna()
    if t.empty:
        return {"overlap_n": 0, "new_after_n": 0}
    end = pd.Timestamp(STAGE_EG_END)
    overlap_n = int((t <= end).sum())
    new_after_n = int((t > end).sum())
    return {"overlap_n": overlap_n, "new_after_n": new_after_n}


def describe_local_csv(path: Path, pair: str) -> dict[str, Any]:
    df = pd.read_csv(path)
    t = pd.to_datetime(df["time"], utc=True, errors="coerce") if "time" in df.columns else pd.Series(dtype="datetime64[ns, UTC]")
    start = t.min().to_pydatetime() if len(t.dropna()) else None
    end = t.max().to_pydatetime() if len(t.dropna()) else None
    ov = overlap_with_stage_eg(t)
    label = classify_period(start, end, exposed=True)
    if ov["new_after_n"] == 0:
        label = PREVIOUSLY_EXAMINED
    elif ov["overlap_n"]:
        label = INDEPENDENCE_NOT_ESTABLISHED
    return {
        "path": str(path).replace("\\", "/"),
        "pair": pair,
        "source": "local_file",
        "content_sha256": sha256_file(path),
        "rows": len(df),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "bid_ask": all(c in df.columns for c in ("bid_close", "ask_close")),
        "overlap_stage_eg": ov,
        "independence_label": label,
        "known_prior_research_exposure": True,
        "revisions": "UNKNOWN",
        "timestamp_convention": "UTC inferred from ISO/pandas",
    }
