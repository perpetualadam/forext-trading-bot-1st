"""Stage 12: one-shot official BLS first-print recovery for usd_empsit_2026-10-02.

Research-only. Official BLS hosts only. Does not enable FORWARD or autonomous BLS collection.
Does not modify prospective consensus observations. First prints live in release_actuals/.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from forex_bot.decision_quality.macro_first_print.catalog import archive_url
from forex_bot.decision_quality.macro_first_print.parse_empsit import parse_empsit_release
from forex_bot.decision_quality.macro_first_print.store import write_raw_release

_REC_PATH = Path(__file__).with_name("_macro_prospective_recorder.py")
_REC_SPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_stage12", _REC_PATH)
R = importlib.util.module_from_spec(_REC_SPEC)
assert _REC_SPEC is not None and _REC_SPEC.loader is not None
_REC_SPEC.loader.exec_module(R)

_S11_PATH = Path(__file__).with_name("_macro_prospective_ingest_stage11.py")
_S11_SPEC = importlib.util.spec_from_file_location("macro_stage11_for_stage12", _S11_PATH)
S11 = importlib.util.module_from_spec(_S11_SPEC)
assert _S11_SPEC is not None and _S11_SPEC.loader is not None
_S11_SPEC.loader.exec_module(S11)

UTC = timezone.utc
EVENT_ID = "usd_empsit_2026-10-02"
T0_UTC = "2026-10-02T12:30:00Z"
RELEASE_DATE = "2026-10-02"
REFERENCE_PERIOD = "2026-09"
PROVIDER = "bls_official"
PROBE_DIR = Path("data/research/macro/consensus_pit/prospective")
OFFICIAL_RAW_DIR = Path("data/research/macro_first_print/raw/bls/employment")
US_PIT_DIR = Path("data/research/macro/us_pit")
ALLOWED_HOSTS = {"www.bls.gov", "bls.gov"}
MAX_BLS_REQUESTS = 10
GENERIC_CURRENT_URL = "https://www.bls.gov/news.release/empsit.htm"
ARCHIVE_HTML = archive_url("EMPLOYMENT_SITUATION", RELEASE_DATE)
ARCHIVE_TXT = ARCHIVE_HTML[:-4] + ".txt"
T15_CHECKPOINT = "T0-15m"
T15_OBSERVED = "2026-10-02T12:16:36Z"
SERIES = (
    ("nonfarm_payroll_change", "nfp", "persons", "SA", "Total nonfarm payroll employment change"),
    ("unemployment_rate", "unemployment", "percent", "SA", "Official U-3 unemployment rate"),
    ("average_hourly_earnings_mom", "ahe_mom", "percent", "SA", "Average hourly earnings, all employees on private nonfarm payrolls, MoM"),
    ("average_hourly_earnings_yoy", "ahe_yoy", "percent", "NSA", "Average hourly earnings, all employees on private nonfarm payrolls, over-the-year"),
)

_AHE_MOM_ALL = re.compile(
    r"average hourly earnings for all employees on private nonfarm payrolls.{0,160}?"
    r"(?:or\s+)?(?P<mom>\d+\.\d+)\s+percent",
    re.I | re.S,
)
_AHE_YOY_ALL = re.compile(
    r"Over the (?:past 12 months|year), average hourly earnings have "
    r"(?P<verb>increased|decreased|rose|fell)\s+by\s+(?P<yoy>\d+\.\d+)\s+percent",
    re.I,
)
_U3 = re.compile(r"unemployment rate(?!s)[^\d]{0,80}(?P<r>\d+\.\d+)\s+percent", re.I)
_U6 = re.compile(r"\bU-6\b", re.I)
_NONSUP = re.compile(r"production and nonsupervisory", re.I)
_ALL_EMP = re.compile(r"all employees on private nonfarm payrolls", re.I)


class RecoveryClosed(RuntimeError):
    pass


class RequestGuard:
    def __init__(self, maximum: int = MAX_BLS_REQUESTS):
        self.maximum = maximum
        self.count = 0
        self.urls: list[str] = []

    def authorize(self, url: str) -> None:
        if self.count >= self.maximum:
            raise RecoveryClosed("BLS_REQUEST_GUARD: request #%s rejected" % (self.count + 1))
        self.count += 1
        self.urls.append(url)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_official_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        raise RecoveryClosed("non-official host refused: %s" % host)
    if "tradingeconomics" in url.lower() or "forexfactory" in url.lower() or "fred.stlouisfed" in url.lower():
        raise RecoveryClosed("non-BLS provider refused")


def is_release_specific_url(url: str) -> bool:
    return "empsit_10022026" in url and "/archives/" in url


def prove_release_identity(url: str, body: bytes) -> dict[str, Any]:
    text = body.decode("utf-8", errors="replace")
    low = text.lower()
    reasons = []
    if not is_release_specific_url(url):
        reasons.append("URL is not the dated official archive empsit_10022026")
    if url.rstrip("/") == GENERIC_CURRENT_URL.rstrip("/"):
        reasons.append("generic mutable current-release URL cannot prove first print")
    if "employment situation" not in low:
        reasons.append("body is not an Employment Situation release")
    if "access denied" in low and "bot activity" in low:
        reasons.append("BLS bot-block page")
    dated = any(
        token in text
        for token in (
            "October 2, 2026",
            "October 02, 2026",
            "Oct. 2, 2026",
            "Friday, October 2, 2026",
        )
    )
    if not dated:
        reasons.append("body does not identify 2026-10-02 publication date")
    parsed = parse_empsit_release(text)
    if parsed.get("reference_period") not in (None, REFERENCE_PERIOD) and parsed.get("reference_period") != REFERENCE_PERIOD:
        reasons.append("reference period is not September 2026")
    title_ok = bool(re.search(r"EMPLOYMENT SITUATION\s*[-\u2013]+\s*SEPTEMBER\s+2026", text, re.I))
    if not title_ok and parsed.get("reference_period") != REFERENCE_PERIOD:
        reasons.append("September 2026 Employment Situation title/reference not proven")
    embargo = parsed.get("embargo_utc")
    if embargo and embargo != T0_UTC:
        reasons.append("embargo clock does not match T0 2026-10-02T12:30:00Z")
    proven = not reasons
    return {
        "proven": proven,
        "status": "PROVEN_FIRST_PRINT" if proven else "NOT_PROVEN",
        "reasons": reasons,
        "parsed_reference_period": parsed.get("reference_period"),
        "embargo_utc": embargo,
        "release_number": parsed.get("release_number"),
    }


def extract_official_components(text: str) -> dict[str, dict[str, Any]]:
    if _U6.search(text) and not _U3.search(text):
        raise RecoveryClosed("unemployment parser rejected U-6-only text")
    if _NONSUP.search(text) and not _ALL_EMP.search(text):
        raise RecoveryClosed("AHE parser rejected production/nonsupervisory-only series")
    parsed = parse_empsit_release(text)
    nfp = parsed.get("nfp_first_print")
    unrate = parsed.get("unemployment_rate_first_print")
    ahe_mom = parsed.get("ahe_mom_first_print")
    ahe_yoy = parsed.get("ahe_yoy_first_print")
    if ahe_mom is None:
        m = _AHE_MOM_ALL.search(text)
        if m and _ALL_EMP.search(m.group(0)):
            ahe_mom = float(m.group("mom"))
    if ahe_yoy is None:
        y = _AHE_YOY_ALL.search(text)
        if y:
            window_before = text[max(0, y.start() - 400) : y.start()]
            if _NONSUP.search(window_before) and not _ALL_EMP.search(window_before):
                raise RecoveryClosed("AHE YoY matched production/nonsupervisory series")
            ahe_yoy = float(y.group("yoy"))
            if y.group("verb").lower() in ("decreased", "fell"):
                ahe_yoy = -abs(ahe_yoy)
    if nfp is None:
        raise RecoveryClosed("ambiguous or missing official NFP first print")
    if unrate is None:
        raise RecoveryClosed("ambiguous or missing official U-3 unemployment rate")
    u3 = _U3.search(text)
    if u3 and abs(float(u3.group("r")) - float(unrate)) > 1e-9:
        raise RecoveryClosed("unemployment extraction did not match first U-3 lead rate")
    return {
        "nfp": {
            "series_name": "nonfarm_payroll_change",
            "actual_first_print": int(nfp),
            "raw": "Total nonfarm payroll employment change %s" % nfp,
            "unit": "persons",
            "seasonal_adjustment": "SA",
            "semantics": SERIES[0][4],
        },
        "unemployment": {
            "series_name": "unemployment_rate",
            "actual_first_print": float(unrate),
            "raw": "Unemployment rate %s percent" % unrate,
            "unit": "percent",
            "seasonal_adjustment": "SA",
            "semantics": SERIES[1][4],
        },
        "ahe_mom": {
            "series_name": "average_hourly_earnings_mom",
            "actual_first_print": None if ahe_mom is None else float(ahe_mom),
            "raw": None if ahe_mom is None else "All-employees AHE MoM %s percent" % ahe_mom,
            "unit": "percent",
            "seasonal_adjustment": "SA",
            "semantics": SERIES[2][4],
            "quality": "PRESENT" if ahe_mom is not None else "NOT_AVAILABLE",
        },
        "ahe_yoy": {
            "series_name": "average_hourly_earnings_yoy",
            "actual_first_print": None if ahe_yoy is None else float(ahe_yoy),
            "raw": None if ahe_yoy is None else "All-employees AHE YoY %s percent" % ahe_yoy,
            "unit": "percent",
            "seasonal_adjustment": "NSA",
            "semantics": SERIES[3][4],
            "quality": "PRESENT" if ahe_yoy is not None else "NOT_AVAILABLE",
        },
    }


def last_observed_surprise(t15: dict | None, first_prints: dict[str, dict]) -> dict[str, Any]:
    if t15 is None or (t15.get("associated_checkpoint_id") or t15.get("checkpoint_id")) != T15_CHECKPOINT:
        return {"available": False, "reason": "last-observed surprise requires the genuine T-15m observation"}
    comps = (t15.get("calendar_fields") or {}).get("components") or {}
    mapping = {
        "nfp": ("nonfarm_payroll_change", "nfp", False),
        "unemployment": ("unemployment_rate", "unemployment", True),
        "ahe_mom": ("average_hourly_earnings_mom", "ahe_mom", True),
        "ahe_yoy": ("average_hourly_earnings_yoy", "ahe_yoy", True),
    }
    out: dict[str, Any] = {
        "available": True,
        "label": "LAST_OBSERVED_SURPRISE",
        "checkpoint_id": T15_CHECKPOINT,
        "observed_at_utc": t15.get("observed_at_utc"),
        "not_strict_final": True,
    }
    for key, (series, actual_key, pp) in mapping.items():
        consensus = (comps.get(series) or {}).get("consensus_value")
        actual = (first_prints.get(actual_key) or {}).get("actual_first_print")
        out["%s_consensus" % key] = consensus
        out["%s_actual" % key] = actual
        if consensus is None or actual is None:
            out["%s_surprise" % key] = None
            out["available"] = False
        else:
            delta = float(actual) - float(consensus)
            out["%s_surprise" % key] = delta
            out["%s_unit" % key] = "percentage_points" if pp else "persons"
            if pp:
                out["%s_surprise_pp" % key] = delta
    return out


def official_get(url: str, guard: RequestGuard, transport: Callable | None = None) -> dict[str, Any]:
    assert_official_url(url)
    guard.authorize(url)
    if transport is not None:
        got = transport(url)
        if int(got.get("status") or 0) == 403:
            raise RecoveryClosed("BLS HTTP 403; official recovery stopped without bypass")
        return got
    req = urllib.request.Request(url, method="GET", headers={"Accept": "text/html, text/plain;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return {
                "url": getattr(resp, "url", url) or url,
                "status": int(getattr(resp, "status", 200) or 200),
                "body": body,
                "content_type": resp.headers.get("Content-Type"),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        if exc.code == 403:
            raise RecoveryClosed("BLS HTTP 403; official recovery stopped without bypass")
        return {"url": url, "status": int(exc.code), "body": body, "content_type": exc.headers.get("Content-Type") if exc.headers else None}
    except urllib.error.URLError as exc:
        raise RecoveryClosed("BLS URL error: %s" % exc.reason)


def discover_official_artifact(guard: RequestGuard, transport: Callable | None = None) -> dict[str, Any]:
    for url in (ARCHIVE_HTML, ARCHIVE_TXT):
        got = official_get(url, guard, transport)
        if got["status"] == 403:
            raise RecoveryClosed("BLS HTTP 403; official recovery stopped without bypass")
        if got["status"] != 200 or not got.get("body"):
            continue
        identity = prove_release_identity(got["url"], got["body"])
        if not identity["proven"]:
            continue
        return {"found": True, "response": got, "identity": identity, "source_url": got["url"]}
    return {"found": False, "response": None, "identity": {"proven": False, "status": "NOT_PROVEN", "reasons": ["no release-specific official artifact proven"]}, "source_url": None}


def _assert_activation_unchanged() -> None:
    cfg = json.loads((PROBE_DIR / "config.json").read_text(encoding="utf-8"))
    if cfg.get("FORWARD_CONSENSUS_COLLECTION_ENABLED") is True:
        raise RecoveryClosed("FORWARD_CONSENSUS_COLLECTION_ENABLED must remain false")
    if cfg.get("OFFICIAL_BLS_FIRST_PRINT_ENABLED") is True:
        raise RecoveryClosed("official BLS autonomous collection must remain disabled")
    if US_PIT_DIR.exists() and not US_PIT_DIR.is_dir():
        raise RecoveryClosed("us_pit path is not a directory")


def recover(
    *,
    rec: R.ProspectiveRecorder | None = None,
    transport: Callable | None = None,
    official_root: Path | None = None,
    live: bool = False,
    artifact_bytes: bytes | None = None,
    source_url: str | None = None,
    http_status: int = 200,
    content_type: str | None = "text/plain",
) -> dict[str, Any]:
    _assert_activation_unchanged()
    rec = rec or R.ProspectiveRecorder(PROBE_DIR)
    prior_obs = (rec.obs_path.read_bytes() if rec.obs_path.exists() else b"")
    t5 = S11.checkpoint_rows(rec, "T0-5m")
    t15_rows = S11.checkpoint_rows(rec, T15_CHECKPOINT)
    t15 = t15_rows[0] if t15_rows else None
    if t15 is not None and rec.root == PROBE_DIR and t15.get("observed_at_utc") != T15_OBSERVED:
        raise RecoveryClosed("T-15m observed_at_utc changed; refusing recovery")
    if t5:
        raise RecoveryClosed("unexpected T-5m observation present; Stage 12 must not create or rewrite it")
    guard = RequestGuard(MAX_BLS_REQUESTS)
    if artifact_bytes is not None:
        url = source_url or ARCHIVE_HTML
        assert_official_url(url)
        identity = prove_release_identity(url, artifact_bytes)
        discovered = {
            "found": identity["proven"],
            "response": {"url": url, "status": http_status, "body": artifact_bytes, "content_type": content_type},
            "identity": identity,
            "source_url": url,
        }
    elif live:
        discovered = discover_official_artifact(guard, transport)
    else:
        discovered = {"found": False, "identity": {"proven": False, "status": "NOT_PROVEN", "reasons": ["live=false"]}, "response": None, "source_url": None}
    if not discovered.get("found"):
        return {
            "status": "NOT_PROVEN",
            "first_print_record_created": False,
            "bls_http_requests": guard.count,
            "bls_urls": guard.urls,
            "identity": discovered.get("identity"),
            "strict_final_surprise": S11.strict_final_surprise(t5m=None, first_prints={}),
            "last_observed_surprise": last_observed_surprise(t15, {}),
        }
    resp = discovered["response"]
    identity = discovered["identity"]
    components = extract_official_components(resp["body"].decode("utf-8", errors="replace"))
    retrieved_at = R.to_utc_iso(rec.now())
    stored = write_raw_release(
        dest_dir=Path(official_root or OFFICIAL_RAW_DIR),
        filename="empsit_10022026.htm" if discovered["source_url"].endswith(".htm") else "empsit_10022026.txt",
        body=resp["body"],
        source_url=discovered["source_url"],
        http_status=resp["status"],
        content_type=resp.get("content_type"),
        publication_date=RELEASE_DATE,
        release_number=identity.get("release_number"),
        retrieved_at=retrieved_at,
    )
    records = []
    for key, spec in (
        ("nfp", SERIES[0]),
        ("unemployment", SERIES[1]),
        ("ahe_mom", SERIES[2]),
        ("ahe_yoy", SERIES[3]),
    ):
        row = components[key]
        if row.get("actual_first_print") is None:
            continue
        out = rec.capture_first_print(
            macro_event_id=EVENT_ID,
            series_name=spec[0],
            actual_first_print=row["actual_first_print"],
            artifact_bytes=resp["body"],
            first_observed_at_utc=retrieved_at,
            unit=row["unit"],
            seasonal_adjustment=row["seasonal_adjustment"],
            reference_period=REFERENCE_PERIOD,
            source_id=PROVIDER,
            notes="Stage 12 official BLS first print. %s. Raw=%s. TE post-release video was not used."
            % (row["semantics"], row["raw"]),
            artifact_suffix="htm" if discovered["source_url"].endswith(".htm") else "txt",
        )
        records.append({"series": spec[0], "result": out, "component": row})
    after_obs = rec.obs_path.read_bytes() if rec.obs_path.exists() else b""
    if after_obs != prior_obs:
        raise RecoveryClosed("consensus observations changed during official recovery")
    surprise = last_observed_surprise(t15, components)
    created_any = any(r["result"].get("status") == "RECORDED" for r in records)
    first_prints = [
        a
        for a in rec.load_actuals()
        if a.get("macro_event_id") == EVENT_ID and a.get("record_kind") == "FIRST_PRINT"
    ]
    if first_prints and not created_any:
        retrieved_at = first_prints[0]["first_observed_at_utc"]
    sidecar = rec.root / "release_actuals" / "usd_empsit_2026-10-02.first_print.json"
    payload = {
        "status": "RECORDED" if created_any else "ALREADY_EXISTS",
        "first_print_record_created": created_any,
        "first_print_record_ids": [a.get("actual_id") for a in first_prints],
        "records": records,
        "components": components,
        "identity": identity,
        "source_url": discovered["source_url"],
        "http_status": resp["status"],
        "retrieved_at_utc": retrieved_at,
        "raw_path": str(stored.body_path).replace("\\", "/"),
        "raw_sha256": stored.sha256,
        "raw_reused": stored.reused,
        "bls_http_requests": guard.count,
        "bls_urls": guard.urls,
        "strict_final_surprise": S11.strict_final_surprise(t5m=None, first_prints=components),
        "last_observed_surprise": surprise,
        "te_post_release_used_as_canonical": False,
        "official_bls_automation_enabled": False,
    }
    if sidecar.exists():
        prev = json.loads(sidecar.read_text(encoding="utf-8"))
        if prev.get("raw_sha256") == stored.sha256 and prev.get("first_print_record_ids") == payload["first_print_record_ids"]:
            prev["bls_http_requests"] = guard.count
            prev["bls_urls"] = guard.urls
            prev["status"] = "ALREADY_EXISTS"
            prev["first_print_record_created"] = False
            prev["records"] = records
            return prev
    sidecar.write_bytes((json.dumps(payload, indent=2, default=str) + "\n").encode("utf-8"))
    return payload


def recover_idempotent(**kwargs) -> dict[str, Any]:
    first = recover(**kwargs)
    second = recover(**kwargs)
    return {"first": first, "second": second}


if __name__ == "__main__":
    result = recover(live=True)
    print("status=%s" % result.get("status"))
    print("created=%s" % result.get("first_print_record_created"))
    print("url=%s" % result.get("source_url"))
    print("sha256=%s" % result.get("raw_sha256"))
    print("requests=%s" % result.get("bls_http_requests"))
    print("identity=%s" % (result.get("identity") or {}).get("status"))
    print("last_observed=%s" % result.get("last_observed_surprise"))
    print("strict_final=%s" % result.get("strict_final_surprise"))
