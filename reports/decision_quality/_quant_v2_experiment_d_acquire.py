"""Download official schedule-metadata pages only. No actuals, consensus, or paid vendors."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

from forex_bot.decision_quality.schedule import RAW_DIR, write_raw

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,text/calendar,application/pdf,*/*"}

SOURCES = [
    ("BLS", "bls.ics", "https://www.bls.gov/schedule/news_release/bls.ics"),
    ("BLS", "cpi.htm", "https://www.bls.gov/schedule/news_release/cpi.htm"),
    ("BLS", "empsit.htm", "https://www.bls.gov/schedule/news_release/empsit.htm"),
    ("BLS", "year_2025.htm", "https://www.bls.gov/schedule/2025/"),
    ("BLS", "year_2026.htm", "https://www.bls.gov/schedule/2026/"),
    ("FRB", "fomccalendars.htm", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"),
    ("FRB", "fomc_schedule_2025_2026.htm", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240809a.htm"),
    ("BOE", "mpc_dates_2025.htm", "https://www.bankofengland.co.uk/news/2024/september/monetary-policy-committee-dates-for-2025"),
    ("BOE", "mpc_dates_2026.htm", "https://www.bankofengland.co.uk/news/2025/september/monetary-policy-committee-dates-for-2026"),
    ("BOE", "upcoming_mpc_dates.htm", "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"),
    ("ONS", "cpi_dataset_current.htm", "https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/consumerpriceinflation/current"),
    ("ONS", "cpi_previous_releases.htm", "https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/previousreleases"),
    ("ONS", "lms_dataset_current.htm", "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/datasets/labourmarketstatistics/current"),
    ("ONS", "labour_previous_releases.htm", "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/uklabourmarket/previousreleases"),
    ("STATCAN", "release_2026.pdf", "https://www150.statcan.gc.ca/n1/release-diffusion/2026-eng.pdf"),
    ("STATCAN", "release_2025.pdf", "https://www150.statcan.gc.ca/n1/release-diffusion/2025-eng.pdf"),
    ("STATCAN", "major_releases.htm", "https://www150.statcan.gc.ca/n1/dai-quo/cal1-eng.htm"),
    ("STATCAN", "upcoming.htm", "https://www150.statcan.gc.ca/n1/dai-quo/cal2-eng.htm"),
    ("BOC", "schedule_2025.htm", "https://www.bankofcanada.ca/2024/08/bank-canada-publishes-2025-schedule-policy-interest-rate-announcements-other-major-publications/"),
    ("BOC", "schedule_2026.htm", "https://www.bankofcanada.ca/2025/08/bank-canada-publishes-2026-schedule-policy-interest-rate-announcements-other-major-publications/"),
    ("BOC", "key_interest_rate.htm", "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/"),
]


def fetch(url: str, timeout: int = 45) -> tuple[int, bytes, str]:
    r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    return r.status_code, r.content, r.url


def main() -> None:
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    log = []
    for agency, filename, url in SOURCES:
        print(f"GET {agency} {filename} {url}", flush=True)
        try:
            status, payload, final = fetch(url)
            rec = {
                "agency": agency,
                "filename": filename,
                "url": url,
                "final_url": final,
                "status": status,
                "bytes": len(payload),
            }
            if status == 200 and payload:
                rec.update(write_raw(agency, filename, payload, final, retrieved))
            log.append(rec)
            print(f"  -> {status} {len(payload)} bytes", flush=True)
        except Exception as exc:
            log.append({"agency": agency, "filename": filename, "url": url, "error": str(exc)})
            print(f"  -> ERROR {exc}", flush=True)
        time.sleep(1.2)
    # StatCan month pages for major releases Sep 2025 - Aug 2026
    for year, months in ((2025, range(9, 13)), (2026, range(1, 9))):
        for month in months:
            url = f"https://www150.statcan.gc.ca/n1/dai-quo/cal1-eng.htm?sm={month}&sy={year}"
            fname = f"major_{year}_{month:02d}.htm"
            print(f"GET STATCAN {fname}", flush=True)
            try:
                status, payload, final = fetch(url)
                rec = {"agency": "STATCAN", "filename": fname, "url": url, "status": status, "bytes": len(payload)}
                if status == 200 and payload:
                    rec.update(write_raw("STATCAN", fname, payload, final, retrieved))
                log.append(rec)
                print(f"  -> {status} {len(payload)} bytes", flush=True)
            except Exception as exc:
                log.append({"agency": "STATCAN", "filename": fname, "url": url, "error": str(exc)})
                print(f"  -> ERROR {exc}", flush=True)
            time.sleep(1.0)
    print("DONE", len(log), "fetches")


if __name__ == "__main__":
    main()
