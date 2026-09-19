"""CLI: python -m forex_bot.decision_quality.download_history

Research-only historical candle cache. Never started by the live bot.
Default is dry-run. A real download requires --confirm.
Default granularity remains M5. M1 writes to data/historical/m1 only.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from forex_bot.decision_quality.history_cache import (
    ALLOWED_GRANULARITIES,
    GRANULARITY_MINUTES,
    RESEARCH_SYMBOLS,
    TimeWindow,
    cache_path,
    default_historical_dir,
    default_m1_historical_dir,
    iter_page_windows,
    last_completed_bar_start,
    last_completed_m5_start,
    read_canonical_csv,
    resume_and_fetch,
    twelve_complete_months_utc,
    validate_frame,
    write_canonical_csv,
)

# Downloader-only page size. Does not change live OANDA_MAX_CANDLES_PER_REQUEST.
DEFAULT_MAX_CANDLES = 2000


def parse_utc(text: str) -> datetime:
    raw = (text or "").strip().replace("Z", "")
    return datetime.fromisoformat(raw)


def plan_range(
    *,
    start: str | None,
    end: str | None,
    now_utc: datetime | None = None,
    bar_minutes: int = 5,
) -> TimeWindow:
    if start and end:
        window = TimeWindow(parse_utc(start), parse_utc(end))
    else:
        a, b = twelve_complete_months_utc(now_utc)
        window = TimeWindow(a, b)
    last_done = last_completed_bar_start(now_utc, bar_minutes)
    if window.end > last_done:
        window = TimeWindow(window.start, last_done)
    return window


def estimate_page_count(window: TimeWindow, max_candles: int, bar_minutes: int) -> int:
    pages = iter_page_windows(window.start, window.end, max_candles=max_candles, bar_minutes=bar_minutes)
    return len(pages)


def format_plan(
    window: TimeWindow,
    symbols: tuple[str, ...],
    data_dir: Path,
    *,
    granularity: str = "M5",
    max_candles: int = DEFAULT_MAX_CANDLES,
) -> str:
    gran = str(granularity or "M5").upper()
    bar_minutes = GRANULARITY_MINUTES[gran]
    pages_each = estimate_page_count(window, max_candles, bar_minutes)
    lines = [
        f"OFFLINE historical {gran} download plan (research only)",
        f"UTC start: {window.start.isoformat()}",
        f"UTC end:   {window.end.isoformat()}  (completed candles only; forming bar excluded)",
        f"symbols:   {', '.join(symbols)}",
        f"granularity: {gran} ({bar_minutes}m bars)",
        f"cache dir: {data_dir.resolve()}",
        f"page size: {max_candles} candles; approx {pages_each} pages/symbol; {pages_each * len(symbols)} pages total",
        "pacing:    sequential pages, extra 0.6s delay after each GET; does not raise OANDA_MAX_REQUESTS_PER_SEC",
        "limiter:   acquire_oanda_rest_slot is in-process only; this CLI cannot share the live bot's limiter",
        "safety:    dry-run unless --confirm is passed",
        "writes:    M1 never overwrites M5 source CSVs",
    ]
    for sym in symbols:
        lines.append(f"  {sym} -> {cache_path(sym, data_dir, granularity=gran)}")
    return "\n".join(lines)


def _fetch_page_factory(
    now_utc: datetime | None,
    request_fn,
    chunk_delay_sec: float,
    granularity: str = "M5",
):
    from forex_bot.oanda_candles_read import paced_request, request_candles_page

    def fetch_page(symbol: str, start: datetime, end: datetime):
        import time

        def wrapped(instrument: str, params: dict) -> dict:
            return paced_request(
                instrument,
                params,
                request_fn=request_fn,
                chunk_delay_sec=chunk_delay_sec,
            )

        last_exc = None
        for attempt in range(5):
            try:
                return request_candles_page(
                    symbol,
                    start,
                    end,
                    request_fn=wrapped,
                    now_utc=now_utc,
                    granularity=granularity,
                )
            except Exception as exc:  # noqa: BLE001 — research download retry only
                last_exc = exc
                wait = min(30.0, 2.0 ** attempt)
                print(f"  retry {attempt + 1}/5 {symbol} {start} after {type(exc).__name__}; sleep {wait}s", flush=True)
                time.sleep(wait)
        raise last_exc

    return fetch_page


def download_symbol(
    symbol: str,
    window: TimeWindow,
    *,
    data_dir: Path,
    fetch_page,
    max_candles: int = DEFAULT_MAX_CANDLES,
    now_utc: datetime | None = None,
    granularity: str = "M5",
) -> dict:
    gran = str(granularity or "M5").upper()
    bar_minutes = GRANULARITY_MINUTES[gran]
    path = cache_path(symbol, data_dir, granularity=gran)
    existing = read_canonical_csv(path) if path.is_file() else None
    if existing is not None and not existing.empty:
        prior = validate_frame(existing, symbol=symbol, granularity=gran, now_utc=now_utc)
        if not prior.ok:
            raise ValueError(f"{path} failed validation: {prior.errors}")
    else:
        import pandas as pd

        existing = pd.DataFrame()
    def _checkpoint(merged_df, page_i, page):
        write_canonical_csv(merged_df, path)
        print(f"  checkpoint {symbol} {gran} page {page_i} bars={len(merged_df)} thru {page.end}", flush=True)

    merged, pages = resume_and_fetch(
        symbol,
        window.start,
        window.end,
        existing=existing,
        fetch_page=fetch_page,
        max_candles=max_candles,
        bar_minutes=bar_minutes,
        on_page=_checkpoint if gran == "M1" else None,
        checkpoint_every=20 if gran == "M1" else 0,
        fill_internal_gaps=gran != "M1",
    )
    if merged.empty:
        raise ValueError(f"{symbol}: no candles after merge")
    report = validate_frame(merged, symbol=symbol, granularity=gran, now_utc=now_utc)
    write_canonical_csv(merged, path)
    return {
        "symbol": symbol,
        "path": str(path),
        "granularity": gran,
        "pages_requested": len(pages),
        "bars": report.bars,
        "ok": report.ok,
        "errors": report.errors,
        "expected_weekend_gaps": report.expected_weekend_gaps,
        "unexpected_gaps": report.unexpected_gaps,
        "earliest": report.earliest.isoformat() if report.earliest else None,
        "latest": report.latest.isoformat() if report.latest else None,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Download/cache OANDA research candles. Default M5.")
    p.add_argument("--start", default=None, help="UTC start YYYY-MM-DDTHH:MM:SS (default: 12 complete months)")
    p.add_argument("--end", default=None, help="UTC end YYYY-MM-DDTHH:MM:SS")
    p.add_argument("--symbols", default=",".join(RESEARCH_SYMBOLS), help="Comma-separated pairs")
    p.add_argument("--data-dir", default=None, help="Cache directory (default: data/historical or data/historical/m1)")
    p.add_argument("--granularity", default="M5", choices=list(ALLOWED_GRANULARITIES))
    p.add_argument("--max-candles", type=int, default=DEFAULT_MAX_CANDLES)
    p.add_argument("--chunk-delay", type=float, default=0.6)
    p.add_argument("--dry-run", action="store_true", help="Print the plan only (default if --confirm omitted)")
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Actually GET candles. Required for a real download.",
    )
    args = p.parse_args(argv)

    symbols = tuple(s.strip().upper().replace("-", "_") for s in args.symbols.split(",") if s.strip())
    unknown = [s for s in symbols if s not in RESEARCH_SYMBOLS]
    if unknown:
        raise SystemExit(f"unsupported symbols: {unknown}; allowed {list(RESEARCH_SYMBOLS)}")
    gran = str(args.granularity).upper()
    bar_minutes = GRANULARITY_MINUTES[gran]
    if args.data_dir:
        data_dir = Path(args.data_dir)
    elif gran == "M1":
        data_dir = default_m1_historical_dir()
    else:
        data_dir = default_historical_dir()
    window = plan_range(start=args.start, end=args.end, bar_minutes=bar_minutes)
    print(
        format_plan(window, symbols, data_dir, granularity=gran, max_candles=args.max_candles),
        flush=True,
    )
    if not args.confirm or args.dry_run:
        print("DRY RUN: no network calls. Re-run with --confirm to download.", flush=True)
        return 0

    fetch_page = _fetch_page_factory(None, None, args.chunk_delay, granularity=gran)
    for symbol in symbols:
        print(f"Downloading {gran} {symbol} ...", flush=True)
        summary = download_symbol(
            symbol,
            window,
            data_dir=data_dir,
            fetch_page=fetch_page,
            max_candles=args.max_candles,
            granularity=gran,
        )
        print(summary, flush=True)
        if not summary["ok"]:
            raise SystemExit(f"validation failed for {symbol}: {summary['errors']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
