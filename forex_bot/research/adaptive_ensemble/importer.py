"""Source-independent import interface. Does not call broker APIs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble.provenance import (
    describe_local_csv,
    sha256_file,
)
from forex_bot.research.adaptive_ensemble.quality import validate_frame

DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL = "DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL"
NO_SAFE_EXTERNAL_SOURCE = "NO_SAFE_EXTERNAL_SOURCE_INVOKED"


@dataclass(frozen=True)
class ImportResult:
    status: str
    pair: str
    frame: pd.DataFrame | None
    provenance: dict[str, Any]
    quality: dict[str, Any] | None
    reason: str | None


def import_local_csv(path: Path, *, pair: str) -> ImportResult:
    if not path.is_file():
        return ImportResult("UNAVAILABLE", pair, None, {"path": str(path)}, None, "missing_file")
    frame = pd.read_csv(path)
    prov = describe_local_csv(path, pair)
    quality = validate_frame(frame, pair=pair)
    return ImportResult("ok", pair, frame, prov, quality, None)


def acquire_external_market_data(*, pair: str, after_iso: str) -> ImportResult:
    """Never invoked against live credentials in Stage G.1.

    An existing GET-only candle helper exists in production (`oanda_candles_read`),
    but using live account credentials, rate limits, and environment selection
    requires explicit operator approval. Stage G.1 does not call it.
    """
    del after_iso
    return ImportResult(
        DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL,
        pair,
        None,
        {
            "source_class": "configured_broker_market_data_unverified_for_g1",
            "pair": pair,
            "invoked": False,
        },
        None,
        NO_SAFE_EXTERNAL_SOURCE,
    )


def data_source_inventory() -> dict[str, Any]:
    hist = Path("data") / "historical"
    local = []
    for csv in sorted(hist.glob("*_M5.csv")) if hist.is_dir() else []:
        pair = csv.name.replace("_M5.csv", "")
        local.append(
            {
                "class": "local_files_already_present",
                "pair": pair,
                "path": str(csv).replace("\\", "/"),
                "sha256": sha256_file(csv),
            }
        )
    return {
        "local_files": local,
        "verified_read_only_public": [],
        "verified_read_only_broker": [],
        "requires_credentials_or_approval": [
            {
                "name": "OANDA InstrumentsCandles GET",
                "module": "forex_bot.oanda_candles_read",
                "status": DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL,
                "reason": "Live credentials, environment, and rate-limit interaction not independently verified as safe for this stage; not called.",
                "invoked": False,
            }
        ],
        "cannot_safely_access": [],
        "post_2026_08_31_local_candles": False,
        "gbp_conversion_series_local": False,
        "synthetic_is_not_market_evidence": True,
    }
