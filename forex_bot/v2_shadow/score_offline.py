"""Offline V2 outcome scoring against the research market store. Never called by bot_loop."""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from forex_bot.v2_shadow.contract import ShadowOutcome, V2ShadowDecision
from forex_bot.v2_shadow.market import REQUIRED_BA, market_dir
from forex_bot.v2_shadow.score import HORIZONS_MIN, _bar_after, score_shadow_decision
from forex_bot.v2_shadow.store import (
    STATUS_ALREADY_EXISTS,
    STATUS_CONFLICT,
    STATUS_STORE_UNSAFE,
    STATUS_WRITTEN,
    append_outcome,
    default_store_dir,
    inspect_outcome_store,
    logical_key,
    logical_outcome_units,
    observations_path,
    outcomes_path,
)

BAR_MINUTES = 5


def _ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def last_completed_m5_start(dt: datetime) -> datetime:
    """Last completed M5 start at observation time. Not the forming candle."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    complete_end = dt - timedelta(minutes=BAR_MINUTES)
    minute = (complete_end.minute // BAR_MINUTES) * BAR_MINUTES
    return complete_end.replace(minute=minute, second=0, microsecond=0)


def decision_from_record(row: dict[str, Any]) -> V2ShadowDecision:
    allowed = {item.name for item in fields(V2ShadowDecision)}
    payload = {k: v for k, v in row.items() if k in allowed}
    return V2ShadowDecision(**payload)


def load_observation_records(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    if not path.is_file():
        return rows, malformed
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            malformed += 1
    return rows, malformed


def market_row_to_bar(row: dict[str, Any]) -> dict[str, Any] | None:
    """Map a persisted complete BA candle to scorer bars. No mid substitute."""
    if not isinstance(row, dict):
        return None
    if row.get("complete") is not True:
        return None
    start = _ts(row.get("candle_start_utc"))
    end = _ts(row.get("candle_end_utc"))
    recorded = _ts(row.get("recorded_at_utc"))
    if start is None:
        return None
    if end is not None and recorded is not None and recorded < end:
        return None
    ba: dict[str, float] = {}
    for name in REQUIRED_BA:
        raw = row.get(name)
        if raw is None:
            return None
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return None
        if val != val or val <= 0:
            return None
        ba[name] = val
    if "close" in row or "mid" in row:
        # Mid may exist on other frames; never copy it into bid/ask.
        pass
    return {
        "ts": start.isoformat(),
        "time": start.isoformat(),
        "candle_start_utc": start.isoformat(),
        **ba,
        "volume": row.get("volume"),
        "complete": True,
    }


def load_market_bars(market_root: Path) -> dict[str, Any]:
    """
    Load complete BA candles. Duplicate (symbol, start) keeps the first row.
    Malformed / incomplete / missing-BA rows are counted and not used.
    """
    stats: dict[str, Any] = {
        "by_symbol": {},
        "bars": {},
        "malformed": 0,
        "duplicates": 0,
        "skipped_incomplete": 0,
        "skipped_no_ba": 0,
    }
    if not market_root.is_dir():
        return stats
    for path in sorted(market_root.glob("*_M5.jsonl")):
        symbol = path.name.replace("_M5.jsonl", "")
        seen: set[str] = set()
        bars: list[dict[str, Any]] = []
        first = last = None
        rows = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                stats["malformed"] += 1
                continue
            rows += 1
            start = str((row or {}).get("candle_start_utc") or "")
            if start and start in seen:
                stats["duplicates"] += 1
                continue
            if start:
                seen.add(start)
            bar = market_row_to_bar(row) if isinstance(row, dict) else None
            if bar is None:
                if isinstance(row, dict) and row.get("complete") is not True:
                    stats["skipped_incomplete"] += 1
                else:
                    stats["skipped_no_ba"] += 1
                continue
            if first is None:
                first = start
            last = start
            bars.append(bar)
        bars.sort(key=lambda b: b["ts"])
        stats["bars"][symbol] = bars
        stats["by_symbol"][symbol] = {
            "rows": rows,
            "usable": len(bars),
            "first": first,
            "last": last,
        }
    return stats


def horizon_has_terminal_bar(decision_ts: datetime, minutes: int, bars: list[dict[str, Any]]) -> bool:
    """
    Existing ``_bar_after`` returns the last bar start in (decision, decision+H].
    That is only a true +H label when a completed bar occupies the last 5 minutes
    of the window. Shorter tapes must not be treated as +240m.
    """
    start = _ts(decision_ts)
    if start is None:
        return False
    target = start + timedelta(minutes=int(minutes))
    chosen = _bar_after(bars, start, int(minutes))
    ts = _ts((chosen or {}).get("ts") or (chosen or {}).get("time"))
    if ts is None:
        return False
    return (target - timedelta(minutes=BAR_MINUTES)) < ts <= target


def mature_outcome(
    outcome: ShadowOutcome,
    *,
    decision_ts: datetime | None = None,
    bars: list[dict[str, Any]] | None = None,
) -> ShadowOutcome | None:
    """Keep only AVAILABLE executable-side labels with a terminal future bar."""
    kept: dict[str, Any] = {}
    for hz, blob in (outcome.horizons or {}).items():
        if not isinstance(blob, dict):
            continue
        try:
            minutes = int(hz)
        except (TypeError, ValueError):
            continue
        if decision_ts is not None and bars is not None:
            if not horizon_has_terminal_bar(decision_ts, minutes, bars):
                continue
        skip = blob.get("skip_opportunity") if isinstance(blob.get("skip_opportunity"), dict) else {}
        new: dict[str, Any] = {}
        new_skip: dict[str, Any] = {}
        buy = blob.get("buy")
        sell = blob.get("sell")
        if isinstance(buy, dict) and buy.get("status") == "AVAILABLE" and buy.get("forward_pips") is not None:
            if buy.get("entry_side") == "ask" and buy.get("exit_side") == "bid":
                new["buy"] = buy
                new_skip["buy_would_cover_cost"] = skip.get("buy_would_cover_cost")
        if isinstance(sell, dict) and sell.get("status") == "AVAILABLE" and sell.get("forward_pips") is not None:
            if sell.get("entry_side") == "bid" and sell.get("exit_side") == "ask":
                new["sell"] = sell
                new_skip["sell_would_cover_cost"] = skip.get("sell_would_cover_cost")
        if new:
            new["skip_opportunity"] = new_skip
            kept[str(hz)] = new
    if not kept:
        return None
    return ShadowOutcome(
        decision_id=outcome.decision_id,
        scored_at_utc=outcome.scored_at_utc,
        model_name=outcome.model_name,
        model_version=outcome.model_version,
        horizons=kept,
        notes=list(outcome.notes) + ["offline_live_market_store", "mature_horizons_only"],
    )


def score_decision_against_market(
    decision: V2ShadowDecision,
    bars: list[dict[str, Any]],
    *,
    scored_at_utc: str | None = None,
) -> ShadowOutcome | None:
    if not bars:
        return None
    raw = score_shadow_decision(decision, bars, scored_at_utc=scored_at_utc)
    start = _ts(decision.timestamp_utc)
    return mature_outcome(raw, decision_ts=start, bars=bars)


def filter_outcome_to_unpersisted_keys(
    outcome: ShadowOutcome,
    existing_keys: dict[str, str],
) -> tuple[ShadowOutcome | None, str, list[str]]:
    """
    Persist-path helper: keep only logical keys not already stored.

    Scoring is unchanged. This avoids the store's partial-overlap CONFLICT
    when a previously scored decision later gains newly matured horizons.
    Matching existing keys are omitted. Mismatched existing keys are conflicts.
    """
    units = logical_outcome_units(outcome.to_dict())
    if not units:
        return None, STATUS_CONFLICT, []
    conflicts = [k for k, canon in units.items() if k in existing_keys and existing_keys[k] != canon]
    if conflicts:
        return None, STATUS_CONFLICT, conflicts
    new_keys = [k for k in units if k not in existing_keys]
    if not new_keys:
        return None, STATUS_ALREADY_EXISTS, []
    new_set = set(new_keys)
    kept: dict[str, Any] = {}
    for hz, blob in (outcome.horizons or {}).items():
        if not isinstance(blob, dict):
            continue
        new_blob: dict[str, Any] = {}
        skip = blob.get("skip_opportunity") if isinstance(blob.get("skip_opportunity"), dict) else {}
        new_skip: dict[str, Any] = {}
        for direction, field, skip_field in (
            ("BUY", "buy", "buy_would_cover_cost"),
            ("SELL", "sell", "sell_would_cover_cost"),
        ):
            key = logical_key(outcome.decision_id, direction, hz)
            if key in new_set and isinstance(blob.get(field), dict):
                new_blob[field] = blob[field]
                if skip_field in skip:
                    new_skip[skip_field] = skip[skip_field]
        if new_blob:
            if new_skip:
                new_blob["skip_opportunity"] = new_skip
            kept[str(hz)] = new_blob
    if not kept:
        return None, STATUS_ALREADY_EXISTS, []
    filtered = ShadowOutcome(
        decision_id=outcome.decision_id,
        scored_at_utc=outcome.scored_at_utc,
        model_name=outcome.model_name,
        model_version=outcome.model_version,
        horizons=kept,
        notes=list(outcome.notes) + ["incremental_new_horizons_only"],
    )
    return filtered, STATUS_WRITTEN, new_keys


def _empty_run() -> dict[str, Any]:
    return {
        "written": 0,
        "already_exists": 0,
        "conflicts": 0,
        "unsafe": 0,
        "skipped_no_mature": 0,
        "skipped_no_market": 0,
        "skipped_bad_decision": 0,
        "observations_seen": 0,
        "logical_labels_written": 0,
        "statuses": [],
        "conflict_keys": [],
    }


def run_offline_score_pass(
    *,
    store_dir: Path | None = None,
    observations_file: Path | None = None,
    market_root: Path | None = None,
    limit: int | None = None,
    scored_at_utc: str | None = None,
    observation_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Score observations from local JSONL. Persist only via append_outcome.
    Does not call OANDA. Does not write observations or market files.
    """
    root = store_dir or default_store_dir()
    obs_path = observations_file or observations_path(root)
    mkt = market_root or market_dir(root)
    report = _empty_run()
    records, malformed = load_observation_records(obs_path)
    report["observation_malformed"] = malformed
    market = load_market_bars(mkt)
    report["market"] = {k: market[k] for k in ("by_symbol", "malformed", "duplicates")}
    wanted = set(observation_ids) if observation_ids else None
    seen = 0
    for row in records:
        if wanted is not None and row.get("decision_id") not in wanted:
            continue
        seen += 1
        if limit is not None and seen > limit:
            break
        report["observations_seen"] += 1
        try:
            decision = decision_from_record(row)
        except (TypeError, ValueError):
            report["skipped_bad_decision"] += 1
            continue
        bars = market["bars"].get(decision.symbol) or []
        if not bars:
            report["skipped_no_market"] += 1
            continue
        outcome = score_decision_against_market(decision, bars, scored_at_utc=scored_at_utc)
        if outcome is None:
            report["skipped_no_mature"] += 1
            continue
        state = inspect_outcome_store(root)
        if not state.safe:
            report["unsafe"] += 1
            report["statuses"].append(STATUS_STORE_UNSAFE)
            break
        persistable, hint, extra = filter_outcome_to_unpersisted_keys(outcome, state.keys)
        if hint == STATUS_CONFLICT:
            report["conflicts"] += 1
            report["conflict_keys"].extend(extra)
            report["statuses"].append(STATUS_CONFLICT)
            continue
        if hint == STATUS_ALREADY_EXISTS or persistable is None:
            report["already_exists"] += 1
            report["statuses"].append(STATUS_ALREADY_EXISTS)
            continue
        result = append_outcome(persistable, store_dir=root)
        report["statuses"].append(result.status)
        if result.status == STATUS_WRITTEN:
            report["written"] += 1
            report["logical_labels_written"] += len(result.keys)
        elif result.status == STATUS_ALREADY_EXISTS:
            report["already_exists"] += 1
        elif result.status == STATUS_CONFLICT:
            report["conflicts"] += 1
            report["conflict_keys"].extend(result.conflict_keys)
        elif result.status == STATUS_STORE_UNSAFE:
            report["unsafe"] += 1
            break
    return report


def summarize_persisted_outcomes(store_dir: Path | None = None) -> list[dict[str, Any]]:
    path = outcomes_path(store_dir)
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows
