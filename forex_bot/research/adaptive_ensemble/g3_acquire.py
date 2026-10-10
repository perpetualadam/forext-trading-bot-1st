"""Stage G.3 bounded candle acquisition. Does not call account or order endpoints."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble.conversion import FxQuote, RateTable
from forex_bot.research.adaptive_ensemble.g3_convert import convert_signed
from forex_bot.research.adaptive_ensemble.oanda_readonly import (
    MIN_INTERVAL_SEC,
    START,
    AuthFailed,
    PageResult,
    RedirectBlocked,
    fetch_candles,
    latest_completed_m5,
    request_plan,
    windows,
)
from forex_bot.research.adaptive_ensemble.protocol import integrity_hash, load_protocol
from forex_bot.research.adaptive_ensemble.provenance import (
    POTENTIALLY_INDEPENDENT,
    overlap_with_stage_eg,
    sha256_file,
)
from forex_bot.research.adaptive_ensemble.quality import validate_frame
from forex_bot.research.adaptive_ensemble.quality_gates import (
    complete_trading_days_after,
    duration_status,
)

G3 = Path("data") / "research" / "adaptive_ensemble" / "g3"
RAW = G3 / "raw"
NORM = G3 / "normalized"
REPORTED_HASH = "539cdc083f83393a79d254d21385edc6c48e88eb0f085d4549df9fdd6d431bc0"


def _env_file(path: Path = Path(".env")) -> dict[str, str]:
    vals: dict[str, str] = {}
    if not path.is_file():
        return vals
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        vals[key.strip()] = value.strip().strip('"').strip("'")
    return vals


def verified_environment(vals: dict[str, str]) -> str:
    mode = (vals.get("TRADING_MODE") or "").strip().lower()
    if mode not in {"live", "practice"}:
        raise RuntimeError("OANDA_ENVIRONMENT_UNVERIFIED")
    return mode


def _token(vals: dict[str, str]) -> str:
    token = (vals.get("OANDA_ACCESS_TOKEN") or vals.get("OANDA_API_KEY") or os.getenv("OANDA_ACCESS_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("OANDA_ENVIRONMENT_UNVERIFIED")
    return token


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _side(block: dict[str, Any] | None, prefix: str) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for src, dst in (("o", "o"), ("h", "h"), ("l", "l"), ("c", "c")):
        key = f"{prefix}_{dst}"
        if not block or src not in block:
            out[key] = None
            continue
        try:
            out[key] = float(block[src])
        except (TypeError, ValueError):
            out[key] = None
    return out


def normalise_pages(pages: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    incomplete = 0
    for page in pages:
        for candle in page.get("candles") or []:
            if not candle.get("complete", False):
                incomplete += 1
                continue
            row = {"time": candle.get("time"), "complete": True}
            row.update(_side(candle.get("bid"), "bid"))
            row.update(_side(candle.get("ask"), "ask"))
            mid = candle.get("mid") or {}
            for src, dst in (("o", "mid_o"), ("h", "mid_h"), ("l", "mid_l"), ("c", "mid_c")):
                if src in mid:
                    try:
                        row[dst] = float(mid[src])
                    except (TypeError, ValueError):
                        row[dst] = None
            rows.append(row)
    frame = pd.DataFrame(rows)
    conflicts = 0
    if not frame.empty:
        frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")
        frame = frame.sort_values("time")
        dup_mask = frame["time"].duplicated(keep=False)
        if dup_mask.any():
            grouped = frame.loc[dup_mask].groupby("time", dropna=False)
            drop_idx: list[Any] = []
            for _, grp in grouped:
                fingerprint = grp.drop(columns=["time"]).astype(str).agg("|".join, axis=1)
                if fingerprint.nunique() > 1:
                    conflicts += len(grp)
                    drop_idx.extend(list(grp.index))
            if drop_idx:
                frame = frame.drop(index=drop_idx)
        frame = frame.drop_duplicates(subset=["time"], keep="first")
    meta = {"incomplete_excluded": incomplete, "conflicts_quarantined": conflicts, "rows": len(frame)}
    return frame, meta


def _with_fallback(frame: pd.DataFrame, name: str, fallback: str) -> pd.Series:
    if name in frame.columns:
        return frame[name].fillna(frame[fallback])
    return frame[fallback]


def quality_for(frame: pd.DataFrame, pair: str) -> dict[str, Any]:
    if frame.empty:
        return {"pair": pair, "status": "FAIL", "rows": 0}
    view = frame.copy()
    view["open"] = _with_fallback(view, "mid_o", "bid_o")
    view["high"] = _with_fallback(view, "mid_h", "bid_h")
    view["low"] = _with_fallback(view, "mid_l", "bid_l")
    view["close"] = _with_fallback(view, "mid_c", "bid_c")
    view["bid_close"] = view["bid_c"]
    view["ask_close"] = view["ask_c"]
    report = validate_frame(view, pair=pair)
    ov = overlap_with_stage_eg(view["time"])
    days = complete_trading_days_after(view)
    report["complete_trading_days_after_cutoff"] = days
    report["duration_status"] = duration_status(days)
    report["overlap_stage_eg"] = ov
    report["independence_label"] = (
        POTENTIALLY_INDEPENDENT if ov["overlap_n"] == 0 and ov["new_after_n"] > 0 else "INDEPENDENCE_NOT_ESTABLISHED"
    )
    missing_ba = int(view["bid_c"].isna().sum() + view["ask_c"].isna().sum())
    if missing_ba:
        report["status"] = "FAIL"
        report["missing_bid_ask"] = missing_ba
    report["promoted_to_validation_ready"] = False
    return report


def quotes_from(frame: pd.DataFrame, pair: str) -> list[FxQuote]:
    out: list[FxQuote] = []
    if frame.empty:
        return out
    for _, row in frame.iterrows():
        bid, ask = row.get("bid_c"), row.get("ask_c")
        if bid is None or ask is None or pd.isna(bid) or pd.isna(ask):
            continue
        if float(bid) <= 0 or float(ask) <= 0 or float(bid) > float(ask):
            continue
        ts = row["time"]
        when = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        out.append(FxQuote(when, pair, float(bid), float(ask), "oanda_m5_bid_ask"))
    return out


def _sample_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    idxs = sorted({0, len(frame) // 2, len(frame) - 1})
    return frame.iloc[idxs]


def conversion_coverage(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    table = RateTable()
    for pair, frame in frames.items():
        for quote in quotes_from(_sample_rows(frame), pair):
            table.add(quote)
    samples: list[dict[str, Any]] = []
    for pair in ("EUR_USD", "GBP_USD", "USD_JPY", "USD_CAD", "USD_CHF", "AUD_USD"):
        frame = frames.get(pair)
        if frame is None or frame.empty:
            samples.append({"pair": pair, "status": "UNAVAILABLE"})
            continue
        when = frame["time"].iloc[len(frame) // 2]
        when_dt = when.to_pydatetime()
        pos = convert_signed(pnl_quote=1.0, pair=pair, when=when_dt, table=table)
        neg = convert_signed(pnl_quote=-1.0, pair=pair, when=when_dt, table=table)
        samples.append(
            {
                "pair": pair,
                "positive_status": pos.status,
                "negative_status": neg.status,
                "positive_path": pos.path,
                "negative_path": neg.path,
            }
        )
    ok = all(s.get("positive_status") == "ok" and s.get("negative_status") == "ok" for s in samples)
    return {"samples": samples, "status": "ok" if ok else "GBP_CONVERSION_UNVERIFIED"}


def save_raw(instrument: str, index: int, page: PageResult, token: str) -> dict[str, Any]:
    dest = RAW / instrument / f"page_{index:03d}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(page.body, sort_keys=True)
    if token and token in text:
        raise RuntimeError("secret appeared in payload")
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, dest)
    candles = page.body.get("candles") or []
    times = [c.get("time") for c in candles if c.get("time")]
    return {
        "instrument": instrument,
        "path": str(dest).replace("\\", "/"),
        "sha256": sha256_file(dest),
        "status": page.status,
        "candles": len(candles),
        "first": times[0] if times else None,
        "last": times[-1] if times else None,
        "url_path": page.url_path,
    }


def acquire(*, end: datetime | None = None) -> dict[str, Any]:
    proto = load_protocol()
    if proto["integrity_hash"] != REPORTED_HASH or integrity_hash(proto) != REPORTED_HASH:
        raise RuntimeError("PROTOCOL_INTEGRITY_BLOCKED")
    vals = _env_file()
    environment = verified_environment(vals)
    token = _token(vals)
    end_at = end or latest_completed_m5()
    if end_at <= START:
        raise RuntimeError("end before approved start")
    plan = request_plan(environment=environment, end=end_at)
    _write(G3 / "request_plan.json", plan)
    _write(
        G3 / "preflight.json",
        {
            "environment": environment,
            "host": plan["host"],
            "token_recorded": False,
            "account_id_recorded": False,
            "read_only_isolation": "standalone_urllib_candle_path_only",
            "protocol_hash_verified": True,
            "broker_calls_before_this_function": False,
        },
    )
    manifests: list[dict[str, Any]] = []
    pages_by_pair: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    requests_made = 0
    for instrument in plan["instruments"]:
        pages_by_pair[instrument] = []
        for start, stop in windows(START, end_at):
            try:
                page = fetch_candles(
                    environment=environment,
                    instrument=instrument,
                    start=start,
                    end=stop,
                    token=token,
                )
            except AuthFailed:
                errors.append({"instrument": instrument, "error": "auth_failed"})
                _write(G3 / "acquisition_manifest.json", {"completed": False, "errors": errors, "requests": requests_made})
                raise
            except RedirectBlocked:
                errors.append({"instrument": instrument, "error": "redirect_blocked"})
                break
            except RuntimeError as exc:
                errors.append({"instrument": instrument, "error": str(exc)[:120]})
                break
            requests_made += 1
            meta = save_raw(instrument, len(pages_by_pair[instrument]), page, token)
            meta["retrieved_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            manifests.append(meta)
            pages_by_pair[instrument].append(page.body)
            time.sleep(MIN_INTERVAL_SEC)
    frames: dict[str, pd.DataFrame] = {}
    qualities = []
    for instrument, pages in pages_by_pair.items():
        frame, norm_meta = normalise_pages(pages)
        frames[instrument] = frame
        if not frame.empty:
            dest = NORM / f"{instrument}_M5.csv"
            dest.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(dest, index=False)
            norm_meta["sha256"] = sha256_file(dest)
            norm_meta["path"] = str(dest).replace("\\", "/")
        q = quality_for(frame, instrument)
        q.update(norm_meta)
        qualities.append(q)
    days = max((int(q.get("complete_trading_days_after_cutoff") or 0) for q in qualities), default=0)
    conv = conversion_coverage(frames)
    digest = hashlib.sha256()
    for item in manifests:
        digest.update(item["sha256"].encode("utf-8"))
    summary = {
        "label": "EXPERIMENTAL_ADAPTIVE_ENSEMBLE_OFFLINE",
        "environment": environment,
        "requests": requests_made,
        "errors": errors,
        "raw_pages": manifests,
        "raw_set_sha256": digest.hexdigest(),
        "quality": qualities,
        "conversion": conv,
        "complete_trading_days": days,
        "duration_status": duration_status(days),
        "strategy_outcomes_inspected": False,
        "models_retuned": False,
    }
    _write(G3 / "acquisition_manifest.json", summary)
    return summary
