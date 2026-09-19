"""Freeze PIT audit sample from Experiment D catalog. No vendor values. No FX outcomes."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CATALOG = Path("data/research/external/normalized/official_schedule_events_d1.json")
OUT = Path("reports/decision_quality/quant_v2_pit_consensus_frozen_sample.json")


def pick(lst, idxs):
    out = []
    n = len(lst)
    for i in idxs:
        j = i if i >= 0 else n + i
        if 0 <= j < n:
            out.append(lst[j])
    return out


def select_frozen_sample(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deterministic first/middle/last by official-clock stratum. No vendor values."""
    prim = sorted(
        [
            r
            for r in rows
            if r.get("in_primary_period")
            and r.get("row_status") == "PRIMARY"
            and r.get("scheduled_precision") == "clock"
        ],
        key=lambda r: (r["currency"], r["category"], r["scheduled_ts_utc"]),
    )
    by = defaultdict(list)
    for r in prim:
        by[(r["currency"], r["category"])].append(r)
    plan = {
        ("USD", "INFLATION"): [0, len(by[("USD", "INFLATION")]) // 2, -1],
        ("USD", "EMPLOYMENT"): [0, len(by[("USD", "EMPLOYMENT")]) // 2, -1],
        ("USD", "CENTRAL_BANK_DECISION"): [0, len(by[("USD", "CENTRAL_BANK_DECISION")]) // 2, -1],
        ("GBP", "INFLATION"): [0, -1],
        ("GBP", "EMPLOYMENT"): [0],
        ("GBP", "CENTRAL_BANK_DECISION"): [0, -1],
        ("CAD", "INFLATION"): [0],
        ("CAD", "EMPLOYMENT"): [0],
        ("CAD", "CENTRAL_BANK_DECISION"): [0, -1],
    }
    sample = []
    for key, idxs in plan.items():
        for r in pick(by[key], idxs):
            sample.append(
                {
                    "sample_id": f"S{len(sample)+1:02d}",
                    "event_id": r["event_id"],
                    "currency": r["currency"],
                    "category": r["category"],
                    "source_agency": r["source_agency"],
                    "source_event_name": r["source_event_name"],
                    "scheduled_ts_utc": r["scheduled_ts_utc"],
                    "scheduled_tz_source": r["scheduled_tz_source"],
                    "selection_rule": f"stratum {key[0]}/{key[1]} chronological indexes {idxs}",
                }
            )
    resched = sorted(
        [r for r in rows if r.get("row_status") == "RESCHEDULED"],
        key=lambda r: r.get("scheduled_ts_utc") or "",
    )
    stress = []
    for r in resched[:2]:
        stress.append(
            {
                "sample_id": f"T{len(stress)+1:02d}",
                "role": "timestamp_stress_only_not_consensus_sample",
                "event_id": r["event_id"],
                "currency": r["currency"],
                "category": r["category"],
                "scheduled_ts_utc": r.get("scheduled_ts_utc"),
                "uncertain_reason": r.get("uncertain_reason"),
                "source_event_name": r["source_event_name"],
            }
        )
    return sample, stress


def main() -> None:
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    sample, stress = select_frozen_sample(rows)
    spec = {
        "frozen_before_vendor_values": True,
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "selection_principle": (
            "Deterministic chronological first/middle/last within Experiment D PRIMARY "
            "in-period strata. USD prioritized. Not selected by FX outcome size."
        ),
        "n_sample": len(sample),
        "events": sample,
        "timestamp_stress_not_for_consensus": stress,
        "pit_acceptance_standard": {
            "required_fields": [
                "event identity",
                "country/currency",
                "event category",
                "scheduled release timestamp",
                "actual release timestamp if available",
                "units",
                "reference period",
                "consensus value",
                "timestamp/vintage of consensus",
                "actual first-print value",
                "previous value as known before release",
                "revision metadata",
                "provider/source identity",
            ],
            "critical_rule": "CONSENSUS MUST BE DEMONSTRABLY PRE-RELEASE. A current webpage historical number is insufficient.",
            "acceptable_pit_proof": [
                "provider timestamped snapshots",
                "historical API vintages",
                "documented immutable pre-release records",
                "provider-certified historical consensus snapshots",
            ],
            "insufficient": "historical row returned today with no vintage semantics",
        },
    }
    OUT.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print("wrote", OUT, "n", len(sample))


if __name__ == "__main__":
    main()
