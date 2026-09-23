"""CLI: python -m forex_bot.decision_quality.trading_economics.download --dry-run

Research-only. Default is dry-run (zero API requests). A live fetch requires
--confirm AND TRADING_ECONOMICS_API_KEY. This module never prints the key.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.decision_quality.trading_economics.client import (
    API_KEY_ENV,
    DryRunTransport,
    fetch_planned,
    public_url,
    read_api_key,
    redact_secret,
    requests_transport,
)
from forex_bot.decision_quality.trading_economics.events import (
    TARGETS,
    horizon_window,
    plan_as_dict,
    plan_requests,
    request_count_note,
)
from forex_bot.decision_quality.trading_economics.schema import normalize_record
from forex_bot.decision_quality.trading_economics.store import (
    default_normalized_dir,
    default_raw_dir,
    write_normalized,
    write_raw_response,
)
from forex_bot.decision_quality.trading_economics.validate import local_family_match, validate_event_vintages


def format_plan(
    *,
    profile: str,
    start: str,
    end: str,
    dest_raw: Path,
    dest_norm: Path,
    requests: list[Any],
    extra: dict[str, Any] | None = None,
) -> str:
    note = request_count_note(len(requests))
    lines = [
        "OFFLINE Trading Economics calendar plan (research only)",
        f"profile:     {profile}",
        f"date range:  {start} -> {end} (UTC dates)",
        "country:     united states",
        "indicators:  inflation rate (CPI family); non farm payrolls (NFP family); "
        "group interest rate (FOMC family)",
        f"request n:   {note['planned_requests']} (lower bound; upper bound UNKNOWN - role row limit unpublished)",
        f"trial cap:   {note['trial_request_cap_documented']} requests / "
        f"{note['trial_datapoint_cap_documented']} data points (pricing page)",
        f"raw dest:    {dest_raw.resolve()}",
        f"norm dest:   {dest_norm.resolve()}",
        "auth:        Authorization header (key never placed in URL or printed)",
        "safety:      dry-run unless --confirm is passed",
        "PIT note:    official PIT page uses the same country/indicator/date URL as historical calendar",
        "",
        "PLANNED REQUESTS",
    ]
    for req in requests:
        lines.append(f"- {req.method} {public_url(req)}")
        lines.append(f"    family={req.family_id} country={req.country} slug={req.slug} kind={req.path_kind}")
        lines.append(f"    dest~ {req.destination_raw_glob}")
    if extra:
        lines.append("")
        lines.append("HORIZON ESTIMATES (same 3-request lower bound; truncation UNKNOWN)")
        for key, value in extra.items():
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def horizon_estimates(*, now_utc: datetime | None = None) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in ("3m", "1y", "3y", "5y", "sample"):
        start, end = horizon_window(name, now_utc=now_utc)
        n = len(plan_requests(start=start, end=end))
        out[name] = f"{start} -> {end}; lower_bound_requests={n}; upper_bound=UNKNOWN"
    return out


def run_download(
    *,
    profile: str,
    confirm: bool,
    data_root: Path,
    now_utc: datetime | None = None,
    transport=None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    start, end = horizon_window(profile, now_utc=now_utc)
    dest_raw = default_raw_dir(data_root)
    dest_norm = default_normalized_dir(data_root)
    requests = plan_requests(start=start, end=end, dest_root=str(dest_raw).replace("\\", "/"))
    plan_text = format_plan(
        profile=profile,
        start=start,
        end=end,
        dest_raw=dest_raw,
        dest_norm=dest_norm,
        requests=requests,
        extra=horizon_estimates(now_utc=now_utc) if profile == "sample" else None,
    )
    result: dict[str, Any] = {
        "dry_run": not confirm,
        "profile": profile,
        "start": start,
        "end": end,
        "requests": [plan_as_dict(r) for r in requests],
        "request_count": request_count_note(len(requests)),
        "plan": plan_text,
        "fetched": [],
    }
    if not confirm:
        result["message"] = "DRY RUN: no network calls. Re-run with --confirm after credentials exist."
        return result

    key = read_api_key(env)
    if not key:
        raise SystemExit(f"--confirm requires {API_KEY_ENV} in the environment. No request was sent.")
    xport = transport or requests_transport
    retrieved = now_utc or datetime.now(timezone.utc)
    retrieved_iso = retrieved.astimezone(timezone.utc).isoformat()
    for req in requests:
        resp, rows = fetch_planned(req, api_key=key, transport=xport)
        stored = write_raw_response(
            raw_dir=dest_raw,
            req=req,
            body=resp.body,
            status=resp.status,
            record_count=len(rows),
            retrieved_at=retrieved,
            response_url=resp.url,
        )
        fam = next(t for t in TARGETS if t.family_id == req.family_id)
        normalized = []
        for row in rows:
            event = normalize_record(row, retrieved_at=retrieved_iso, raw_sha256=stored.sha256)
            matched = local_family_match(event.event, event.category, fam.local_name_hints)
            payload = event.to_dict()
            payload["local_family_match"] = matched
            payload["pit"] = validate_event_vintages([event]).to_dict()
            normalized.append(payload)
        norm_name = f"{retrieved.strftime('%Y%m%dT%H%M%SZ')}_{req.family_id}_{stored.sha256[:16]}.json"
        write_normalized(dest_norm / norm_name, normalized)
        result["fetched"].append(
            {
                "family_id": req.family_id,
                "http_status": resp.status,
                "record_count": len(rows),
                "sha256": stored.sha256,
                "raw_file": stored.body_path.name,
                "matched_local_hints": sum(1 for n in normalized if n["local_family_match"]),
            }
        )
    result["message"] = "FETCH COMPLETE (research store only; not joined to live bot)"
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Research-only Trading Economics calendar downloader.")
    p.add_argument("--dry-run", action="store_true", help="Print the plan only (also the default).")
    p.add_argument("--confirm", action="store_true", help="Actually GET. Requires TRADING_ECONOMICS_API_KEY.")
    p.add_argument(
        "--profile",
        default="sample",
        choices=("sample", "3m", "1y", "3y", "5y"),
        help="sample = first validation window (~18 months). Do not use 5y on the first key run.",
    )
    p.add_argument("--data-dir", default="data/research/trading_economics")
    args = p.parse_args(argv)

    confirm = bool(args.confirm) and not bool(args.dry_run)
    if args.confirm and args.profile != "sample":
        print(
            "REFUSING: first authenticated run must use --profile sample. "
            "Longer horizons are dry-run planning only until PIT validation passes.",
            flush=True,
        )
        if confirm:
            return 2

    payload = run_download(
        profile=args.profile,
        confirm=confirm and args.profile == "sample",
        data_root=Path(args.data_dir),
        transport=None if confirm and args.profile == "sample" else DryRunTransport(),
    )
    print(redact_secret(payload["plan"]), flush=True)
    print(payload["message"], flush=True)
    if confirm and args.profile == "sample":
        print(json.dumps({"fetched": payload["fetched"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
