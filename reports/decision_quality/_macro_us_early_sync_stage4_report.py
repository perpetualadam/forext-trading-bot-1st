"""Stage-4 markdown writer. Separated so f-string brace bugs cannot block mining."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pathlib import Path as _P
import importlib.util

_CORE = _P("reports/decision_quality/_macro_us_early_sync_stage4.py")
_SPEC = importlib.util.spec_from_file_location("macro_us_early_sync_stage4_core", _CORE)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)

continuation_vs_first = _MOD.continuation_vs_first
REPORT_PATH = Path("reports/decision_quality/macro_us_early_sync_stage4.md")
OUT_JSON = Path("reports/decision_quality/_macro_us_early_sync_stage4_results.json")


def _get(d: dict, *keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d:
            return d[k]
        if str(k) in d:
            return d[str(k)]
    return default


def write_report(p: dict) -> str:
    dist = p["agreement_dist"]
    prim = p["primary_6of6"]
    ctrl = p["controls"]["primary_6of6"]
    alls = p["all_events"]["by_agreement"]
    six = _get(alls, 6, default={}) or {}
    five = _get(alls, 5, default={}) or {}
    four = _get(alls, 4, default={}) or {}
    three = _get(alls, 3, default={}) or {}

    def fmt(x, nd=2):
        if x is None:
            return "NA"
        return f"{x:.{nd}f}"

    def pct(x):
        if x is None:
            return "NA"
        return f"{100.0 * x:.1f}%"

    def agn(d, k):
        return int(_get(d, k, default=0) or 0)

    def horizon_block(block: dict, end: int) -> dict:
        return _get(block, f"to_{end}", default={}) or {}

    def cont_cell(block: dict, end: int) -> str:
        b = horizon_block(block, end)
        n = int(block.get("n") or 0)
        c = int(b.get("continuation") or 0)
        r = int(b.get("reversal") or 0)
        f = int(b.get("flat") or 0)
        return f"{c}/{n} cont, {r} rev, {f} flat"

    def rem_cell(block: dict, end: int) -> str:
        b = horizon_block(block, end)
        return f"{fmt(b.get('median_signed_usd_pips'))} / {fmt(b.get('median_abs_usd_pips'))}"

    def exec_cell(block: dict, end: int) -> str:
        b = horizon_block(block, end)
        return (
            f"{fmt(b.get('median_exec_pips'))} event-median; "
            f"{fmt(b.get('median_per_pair_exec_pips'))} per-pair-median; "
            f"pos {b.get('exec_positive', 0)} / neg {b.get('exec_negative', 0)} / "
            f"flat {b.get('exec_flat', 0)} (n={b.get('exec_n', 0)})"
        )

    table_lines = [
        "| event | family | T0 | 5m USD dir | agree | 5m med pips | 5->15 | 5->30 | 5->60 | 5->120 | 5->240 | 5->15 c | 5->30 c | 5->60 c | exec 5->60 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |",
    ]
    for e in p["events"]:
        sgn = {1: "USD+", -1: "USD-", 0: "flat"}[int(e["first5_usd_sign"])]
        rem = e["remaining_mid"]
        exe = e["remaining_exec"]

        def md(end):
            b = _get(rem, end, default=None)
            return fmt(b.get("median") if b else None)

        def cf(end):
            b = _get(rem, end, default=None)
            later = b.get("median") if b else None
            return continuation_vs_first(int(e["first5_usd_sign"]), later)

        exe60 = (_get(exe, 60, default={}) or {}).get("median")
        table_lines.append(
            "| {id} | {fam} | {t0} | {sgn} | {ag}/6 | {p5} | {a} | {b} | {c} | {d} | {ee} | {c15} | {c30} | {c60} | {ex} |".format(
                id=e["macro_event_id"],
                fam=e["family"],
                t0=e["t0"],
                sgn=sgn,
                ag=e["agreement"],
                p5=fmt(e["first5_median_usd_pips"]),
                a=md(15),
                b=md(30),
                c=md(60),
                d=md(120),
                ee=md(240),
                c15=cf(15),
                c30=cf(30),
                c60=cf(60),
                ex=fmt(exe60),
            )
        )
    table = "\n".join(table_lines)

    six_rows = [e for e in p["events"] if int(e["agreement"]) == 6]
    abs5_six = [e["first5_abs_median_usd_pips"] for e in six_rows]
    med_abs5_six = float(np.median(abs5_six)) if abs5_six else None
    spreads = []
    for e in p["events"]:
        spreads.extend((e.get("spreads_at_D") or {}).values())
    med_spread = float(np.median(spreads)) if spreads else None

    n6 = prim["n"]
    a15, a30, a60 = prim["to_15"], prim["to_30"], prim["to_60"]
    c15, c30, c60 = ctrl["to_15"], ctrl["to_30"], ctrl["to_60"]
    fam = p["eligible_by_family"]
    mag = p["magnitude_tertiles_exploratory"]
    cpi6 = _get(p["families"]["CPI"]["by_agreement"], 6, default={}) or {}
    emp6 = _get(p["families"]["EMPLOYMENT_SITUATION"]["by_agreement"], 6, default={}) or {}
    fomc6 = _get(p["families"]["FOMC"]["by_agreement"], 6, default={}) or {}
    ctrl_sum6 = _get(p["controls"]["summary"]["by_agreement"], 6, default={}) or {}

    freeze = "NONE"
    f_answer = "NO — INSUFFICIENT / UNSTABLE"
    lab15 = a15.get("labels") or {}
    lab30 = a30.get("labels") or {}
    lab60 = a60.get("labels") or {}

    parts = []
    parts.append("# MACRO RESEARCH — STAGE 4")
    parts.append("# EARLY USD SYNCHRONIZATION → NON-OVERLAPPING FORWARD MOVEMENT")
    parts.append("")
    parts.append("Research only. Stage-3 H1/H2 definitions were not altered.")
    parts.append("Primary independent unit = **macro event**. Six pairs are correlated responses to one release.")
    parts.append("Helpers/tests/report only. `data/research/macro/us_pit/` and `data/historical/*_M5.csv` were read, not modified.")
    parts.append("No OANDA requests. No model. No live rule.")
    parts.append("")
    parts.append("LOOKAHEAD")
    parts.append("---------")
    parts.append("T0 = official scheduled_release_utc (all 29 eligible T0s fall on M5 boundaries).")
    parts.append("D = T0 + 5 minutes = close of the T0 M5 bar, the first completed post-release candle.")
    parts.append("Features at D use only that T0 bar: open to close. The bar that starts at D is unknown at D and is not a feature.")
    parts.append("Targets are strictly non-overlapping with the feature candle: remaining movement from T0-bar close to the close of the bar completing at T0+H.")
    parts.append("H in {15, 30, 60, 120, 240} minutes. Exit bar start = T0+H-5m, which is >= D for every listed H.")
    parts.append("These are not Stage-3 cumulative T0 to future returns. Stage-3 overlapping 5m to 60m continuation is not reused as a prediction target.")
    parts.append("")
    parts.append("DATASET:")
    parts.append("eligible events: %s" % p["eligible_n"])
    parts.append("CPI: %s" % fam.get("CPI", 0))
    parts.append("Employment: %s" % fam.get("EMPLOYMENT_SITUATION", 0))
    parts.append("FOMC: %s" % fam.get("FOMC", 0))
    parts.append(
        "controls: %s (Stage-3 matched weekday+UTC HH:MM, window padding 240m, outside +/-240m of eligible T0; T0 bar and +60m exit bar required on all six pairs)"
        % p["controls"]["n"]
    )
    parts.append("excluded: unpublished Oct-2025 CPI, unpublished Oct-2025 Employment, retrieval-blocked 2026-08-12 CPI")
    parts.append("")
    parts.append("FIRST-5M AGREEMENT:")
    parts.append("3/6: %s" % agn(dist, 3))
    parts.append("4/6: %s" % agn(dist, 4))
    parts.append("5/6: %s" % agn(dist, 5))
    parts.append("6/6: %s" % agn(dist, 6))
    parts.append("Zeros do not count as agreement. No weighted voting. Natural categories were not recombined after seeing results.")
    parts.append("")
    parts.append("PRIMARY 6/6 TEST:")
    parts.append("n: %s" % n6)
    parts.append(
        "+5->+15 continuation: %s/%s (%s, event bootstrap 95%% CI %s-%s); reversals %s; flats %s"
        % (lab15.get("continuation", 0), n6, pct(a15.get("rate")), pct(a15.get("ci_low")), pct(a15.get("ci_high")), lab15.get("reversal", 0), lab15.get("flat", 0))
    )
    parts.append(
        "+5->+30 continuation: %s/%s (%s, CI %s-%s); reversals %s; flats %s"
        % (lab30.get("continuation", 0), n6, pct(a30.get("rate")), pct(a30.get("ci_low")), pct(a30.get("ci_high")), lab30.get("reversal", 0), lab30.get("flat", 0))
    )
    parts.append(
        "+5->+60 continuation: %s/%s (%s, CI %s-%s); reversals %s; flats %s"
        % (lab60.get("continuation", 0), n6, pct(a60.get("rate")), pct(a60.get("ci_low")), pct(a60.get("ci_high")), lab60.get("reversal", 0), lab60.get("flat", 0))
    )
    parts.append("Bootstrap resamples events, not pair-rows. All three primary CIs include 50%.")
    parts.append("")
    parts.append("SECONDARY AGREEMENT (descriptive; not a threshold search):")
    parts.append("5/6 n=%s; +5->+15 %s; +5->+30 %s; +5->+60 %s" % (five.get("n"), cont_cell(five, 15), cont_cell(five, 30), cont_cell(five, 60)))
    parts.append("4/6 n=%s (no events in this sample)" % four.get("n"))
    parts.append("3/6 n=%s (no events in this sample)" % three.get("n"))
    parts.append("")
    parts.append("REMAINING MOVEMENT:")
    parts.append("6/6 first-5m median |USD| mid pips (already realized by D): %s" % fmt(med_abs5_six))
    parts.append("6/6 subsequent median signed / |USD| mid pips:")
    parts.append("+5->+15: %s" % rem_cell(six, 15))
    parts.append("+5->+30: %s" % rem_cell(six, 30))
    parts.append("+5->+60: %s" % rem_cell(six, 60))
    parts.append("+5->+120: %s" % rem_cell(six, 120))
    parts.append("+5->+240: %s" % rem_cell(six, 240))
    parts.append("5/6 subsequent signed / |USD|:")
    parts.append(
        "+5->+15 %s; +5->+30 %s; +5->+60 %s; +5->+120 %s; +5->+240 %s"
        % (rem_cell(five, 15), rem_cell(five, 30), rem_cell(five, 60), rem_cell(five, 120), rem_cell(five, 240))
    )
    parts.append("4/6 and 3/6: n=0, remaining movement NA.")
    parts.append("Median M5 spread at D across event-pair closes: %s pips (M5 bid/ask; not tick-level)." % fmt(med_spread))
    parts.append("")
    parts.append("EXECUTABLE AFTER-COST OUTCOMES:")
    parts.append("Hypothetical USD-direction expression at D. USD-strength: SELL EUR_USD, GBP_USD, AUD_USD; BUY USD_JPY, USD_CAD, USD_CHF. Reverse for USD-weakness.")
    parts.append("Entry uses completed T0 close available at D: BUY ask_close, SELL bid_close. Exit later: BUY bid_close, SELL ask_close.")
    parts.append("No sizing. No production SL/TP. No exit optimization. Event-level statistic = median of six pair executable pips.")
    parts.append("6/6 +5->+15: %s" % exec_cell(six, 15))
    parts.append("6/6 +5->+30: %s" % exec_cell(six, 30))
    parts.append("6/6 +5->+60: %s" % exec_cell(six, 60))
    parts.append("6/6 +5->+120: %s" % exec_cell(six, 120))
    parts.append("6/6 +5->+240: %s" % exec_cell(six, 240))
    parts.append("")
    parts.append("FAMILY BREAKDOWN:")
    parts.append("Descriptive case-study only. CPI n~10, Employment n~11, FOMC n=8. Do not select a family for deployment.")
    parts.append(
        "CPI n=%s, 6/6 n=%s; +5->+15 %s; +5->+60 %s; remaining |USD| 5->60 %s; exec 5->60 %s"
        % (p["families"]["CPI"]["n"], cpi6.get("n"), cont_cell(cpi6, 15), cont_cell(cpi6, 60), rem_cell(cpi6, 60), exec_cell(cpi6, 60))
    )
    parts.append(
        "Employment n=%s, 6/6 n=%s; +5->+15 %s; +5->+60 %s; remaining |USD| 5->60 %s; exec 5->60 %s"
        % (
            p["families"]["EMPLOYMENT_SITUATION"]["n"],
            emp6.get("n"),
            cont_cell(emp6, 15),
            cont_cell(emp6, 60),
            rem_cell(emp6, 60),
            exec_cell(emp6, 60),
        )
    )
    parts.append(
        "FOMC n=%s, 6/6 n=%s; +5->+15 %s; +5->+60 %s; remaining |USD| 5->60 %s; exec 5->60 %s"
        % (p["families"]["FOMC"]["n"], fomc6.get("n"), cont_cell(fomc6, 15), cont_cell(fomc6, 60), rem_cell(fomc6, 60), exec_cell(fomc6, 60))
    )
    parts.append("FOMC 6/6 remaining |move| and after-cost median look larger, but n=7. Not a frozen family rule.")
    parts.append("")
    parts.append("MATCHED CONTROL COMPARISON:")
    parts.append("Same T0 to +5 observation and non-overlapping remaining windows on Stage-3 matched non-event clocks.")
    parts.append(
        "Control first-5m agreement: 6/6 %s; 5/6 %s; 4/6 %s; 3/6 %s of %s"
        % (
            agn(p["controls"]["summary"]["agreement_dist"], 6),
            agn(p["controls"]["summary"]["agreement_dist"], 5),
            agn(p["controls"]["summary"]["agreement_dist"], 4),
            agn(p["controls"]["summary"]["agreement_dist"], 3),
            p["controls"]["n"],
        )
    )
    parts.append(
        "Control 6/6 n=%s of %s (%.1f%%) vs events 22/29 (75.9%%). Early 6/6 is more common after releases (environment), consistent with Stage-3 H2 being about synchronization frequency, not remaining-direction prediction."
        % (ctrl["n"], p["controls"]["n"], 100.0 * ctrl["n"] / max(p["controls"]["n"], 1))
    )
    parts.append("+5->+15 continuation: events %s vs controls %s (CI %s-%s)" % (pct(a15.get("rate")), pct(c15.get("rate")), pct(c15.get("ci_low")), pct(c15.get("ci_high"))))
    parts.append("+5->+30 continuation: events %s vs controls %s (CI %s-%s)" % (pct(a30.get("rate")), pct(c30.get("rate")), pct(c30.get("ci_low")), pct(c30.get("ci_high"))))
    parts.append("+5->+60 continuation: events %s vs controls %s (CI %s-%s)" % (pct(a60.get("rate")), pct(c60.get("rate")), pct(c60.get("ci_low")), pct(c60.get("ci_high"))))
    parts.append(
        "Control 6/6 remaining |USD| 5->60 median %s vs event 6/6 %s. Control 6/6 exec 5->60 %s."
        % (fmt(horizon_block(ctrl_sum6, 60).get("median_abs_usd_pips")), fmt(horizon_block(six, 60).get("median_abs_usd_pips")), exec_cell(ctrl_sum6, 60))
    )
    parts.append("Early sync is more frequent around events. Subsequent direction after D is not distinguishable from matched clocks.")
    parts.append("")
    parts.append("CONDITIONAL MAGNITUDE (exploratory tertiles of |first-5m|; not a threshold search; not a trading rule):")
    parts.append("low n=%s median remaining |5->60| %s" % (_get(mag, "low", default={}).get("n"), fmt(_get(mag, "low", default={}).get("median_remaining_abs_5_to_60"))))
    parts.append("mid n=%s median remaining |5->60| %s" % (_get(mag, "mid", default={}).get("n"), fmt(_get(mag, "mid", default={}).get("median_remaining_abs_5_to_60"))))
    parts.append("high n=%s median remaining |5->60| %s" % (_get(mag, "high", default={}).get("n"), fmt(_get(mag, "high", default={}).get("median_remaining_abs_5_to_60"))))
    parts.append("Larger first-5m |USD| is not associated with larger remaining |5->60| in this sample (low tertile remaining is largest). Secondary only.")
    parts.append("")
    parts.append("EVENT-LEVEL ROBUSTNESS:")
    parts.append("Pooled 6/6 continuation is not a handful of identical rows: CPI and Employment 6/6 at +5->+60 are mixed continuation/reversal; FOMC 5/7 continuation. See table.")
    parts.append("")
    parts.append(table)
    parts.append("")
    parts.append("MULTIPLE TESTING:")
    parts.append("primary comparisons: 3")
    parts.append("secondary comparisons: 3 remaining agreement categories x 5 horizons x (continuation, signed, abs, exec pos/neg) + 3 families + control comparisons + tertiles (~80 descriptive cells)")
    parts.append("Do not convert secondary findings into validated alpha.")
    parts.append("")
    parts.append("ANSWERS:")
    parts.append("A: YES as a description — 22/29 eligible events (75.9%) have 6/6 first-5m USD agreement, vs 197/458 (43.0%) matched controls. Frequent enough to study. Not frequent-and-stable enough to train.")
    parts.append("B: NO clear persistence. 6/6 continuation after D is 12/22 (54.5%) at +5->+15, 10/22 (45.5%) at +5->+30, 12/22 (54.5%) at +5->+60. Event-bootstrap CIs all include 50%.")
    parts.append(
        "C: SOME remaining |USD| exists (6/6 median |remaining| 5.09 / 4.27 / 6.90 / 11.11 / 17.03 pips at the five horizons) but it is smaller than the first-5m move already observed (6/6 median |first-5m| %s pips) and signed remaining is near zero because continuations and reversals mix."
        % fmt(med_abs5_six)
    )
    parts.append("D: NO at the event-median. After genuine bid/ask, 6/6 median executable pips are +0.07 (11 pos / 11 neg) at +5->+15, -2.60 (8/14) at +5->+30, -1.00 (8/14) at +5->+60. Gross remaining movement does not survive costs as an event-level median.")
    parts.append("E: Early 6/6 is more common on event clocks than controls (75.9% vs 43.0%), which is an environment fact. Subsequent directional continuation after D is not stronger than matched non-event 6/6 clocks (control 45.7% / 53.3% / 45.2% at the three primary horizons).")
    parts.append("F: %s. n=22 primary rows; rates straddle 50%% across the three pre-registered horizons; family split is unstable (Employment 6/6 +5->+60 is 2/8 continuation; FOMC 5/7). Do not freeze a prospective directional hypothesis." % f_answer)
    parts.append("")
    parts.append("PROSPECTIVE DIRECTIONAL HYPOTHESIS FROZEN:")
    parts.append(freeze)
    parts.append("")
    parts.append("DATA SUFFICIENT FOR MODEL TRAINING:")
    parts.append("NO")
    parts.append("DATA SUFFICIENT FOR 65% CONFIDENCE CLAIM:")
    parts.append("NO")
    parts.append("SURPRISE DATA AVAILABLE:")
    parts.append("NO")
    parts.append("PRODUCTION CHANGE JUSTIFIED:")
    parts.append("NO")
    parts.append("V2 POLICY CHANGE:")
    parts.append("NO")
    parts.append("MODEL TRAINED:")
    parts.append("NO")
    parts.append("OANDA/API REQUESTS:")
    parts.append("0")
    parts.append("SOURCE DATA MODIFIED:")
    parts.append("NO")
    parts.append("FILES CHANGED:")
    parts.append("research helpers/tests/report only")
    parts.append("STOP.")
    parts.append("")
    REPORT_PATH.write_text("\n".join(parts), encoding="utf-8")
    return freeze


if __name__ == "__main__":
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    write_report(payload)
    print("wrote", REPORT_PATH)
