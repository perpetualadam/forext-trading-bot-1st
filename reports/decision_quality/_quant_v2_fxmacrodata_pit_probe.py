"""Tiny no-key FXMacroData provenance probe. No FX join. No purchase."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

BASE = "https://api.fxmacrodata.com"
ROOT = Path("data/research/external/fxmacrodata_probe")
RAW = ROOT / "raw"
NORM = ROOT / "normalized"
SAMPLE_IDS = Path("reports/decision_quality/quant_v2_fxmacrodata_frozen_recent_usd_ids.json")
TIMEOUT = 30
UA = "QuantV2PITProbe/1.0 research-inspection"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_raw(name: str, url: str, resp: requests.Response) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    retrieved = utc_now()
    body = resp.content
    dest = RAW / f"{name}.json"
    dest.write_bytes(body)
    identity = {
        "name": name,
        "url": url,
        "retrieved_at_utc": retrieved,
        "status_code": resp.status_code,
        "content_type": resp.headers.get("Content-Type"),
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "path": str(dest).replace("\\", "/"),
    }
    (RAW / f"{name}.identity.json").write_text(json.dumps(identity, indent=2), encoding="utf-8")
    return identity


def get(path: str, params: dict | None = None) -> tuple[dict, requests.Response]:
    q = f"?{urlencode(params)}" if params else ""
    url = f"{BASE}{path}{q}"
    resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA, "Accept": "application/json"})
    name = path.strip("/").replace("/", "_")
    if params:
        name += "_" + "_".join(f"{k}-{v}" for k, v in params.items())
    identity = save_raw(name, url, resp)
    return identity, resp


def main() -> None:
    log: list[dict] = []

    for path in (
        "/v1/predictions/coverage",
        "/v1/predictions/coverage/usd",
        "/v1/data_catalogue/usd",
        "/v1/calendar/usd",
    ):
        ident, resp = get(path)
        log.append({**ident, "stage": "coverage_or_discovery"})
        print(ident["status_code"], ident["url"], ident["bytes"])

    # Announcement metadata only, tiny recent windows. Persist IDs before predictions.
    announcement_ids: list[dict] = []
    for slug, category in (
        ("inflation", "INFLATION"),
        ("non_farm_payrolls", "EMPLOYMENT"),
        ("policy_rate", "CENTRAL_BANK_DECISION"),
    ):
        ident, resp = get(f"/v1/announcements/usd/{slug}", {"limit": "3"})
        log.append({**ident, "stage": "announcement_metadata"})
        print(ident["status_code"], ident["url"], ident["bytes"])
        if resp.status_code == 401:
            log.append({"stage": "stop_paid_auth", "url": ident["url"]})
            continue
        if resp.status_code != 200:
            continue
        try:
            payload = resp.json()
        except ValueError:
            continue
        rows = payload.get("data") or []
        if rows:
            row = rows[0]
            announcement_ids.append(
                {
                    "selection_rule": "most_recent_row_in_no_key_announcements_limit_3",
                    "category": category,
                    "indicator": slug,
                    "announcement_id": row.get("announcement_id"),
                    "date": row.get("date"),
                    "announcement_datetime": row.get("announcement_datetime"),
                    "announcement_datetime_local": row.get("announcement_datetime_local"),
                    "selected_before_prediction_values": True,
                }
            )

    SAMPLE_IDS.write_text(
        json.dumps(
            {
                "frozen_before_prediction_values": True,
                "frozen_at_utc": utc_now(),
                "selection_principle": (
                    "Most recent eligible completed USD announcement per "
                    "INFLATION / EMPLOYMENT / CENTRAL_BANK_DECISION from no-key "
                    "announcements?limit=3. Not selected by FX outcome."
                ),
                "n_sample": len(announcement_ids),
                "events": announcement_ids,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("wrote", SAMPLE_IDS, "n", len(announcement_ids))

    # Tiny prediction probes. Stop a path on paid auth.
    for slug, extra in (
        ("inflation", {"prediction_class": "compiled_consensus", "limit": "3"}),
        ("inflation", {"prediction_class": "forecaster_survey", "limit": "3"}),
        ("non_farm_payrolls", {"prediction_class": "compiled_consensus", "limit": "3"}),
        ("policy_rate", {"prediction_class": "compiled_consensus", "limit": "3"}),
        ("policy_rate_midpoint", {"prediction_class": "forecaster_survey", "limit": "3"}),
    ):
        ident, resp = get(f"/v1/predictions/usd/{slug}", extra)
        log.append({**ident, "stage": "prediction_probe"})
        print(ident["status_code"], ident["url"], ident["bytes"])
        if resp.status_code in (401, 402, 403):
            log.append({"stage": "stop_paid_auth", "url": ident["url"], "status_code": resp.status_code})
            print("STOP paid/auth", ident["url"], resp.status_code)

    NORM.mkdir(parents=True, exist_ok=True)
    (NORM / "request_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print("requests", len(log))


if __name__ == "__main__":
    main()
