from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

p = json.loads(
    Path("reports/decision_quality/_sl_on_fill_analysis.json").read_text(encoding="utf-8")
)
print("=== CANCEL xref vs M1 exec side ===")
for x in p["cancelled"]:
    pip = 0.01 if "JPY" in x["instrument"] else 0.0001
    exec_m1 = x["m1_ask_c"] if x["side"] == "BUY" else x["m1_bid_c"]
    lab = "ask" if x["side"] == "BUY" else "bid"
    d = None if exec_m1 is None else (x["implied_xref"] - exec_m1) / pip
    print(
        x["instrument"],
        x["side"],
        "xref",
        round(x["implied_xref"], 5),
        lab,
        exec_m1,
        "d_pips",
        None if d is None else round(d, 2),
        "spr",
        round(x["m1_spread_pips"], 2),
        "stop",
        round(x["stop_pips"], 2),
        "trigH",
        round(x["headroom_vs_m1_trigger_pips"], 2),
    )
print("=== SUCCESS ===")
for x in p["successful"]:
    print(
        x["instrument"],
        x["side"],
        "stop",
        round(x["stop_pips"], 2),
        "spr",
        None if x["spread_pips"] is None else round(x["spread_pips"], 2),
        "ratio",
        None if x["stop_over_spread"] is None else round(x["stop_over_spread"], 2),
        "fillR",
        None if x["fill_r"] is None else round(x["fill_r"], 3),
        "dbms",
        None if x["db_to_tx_ms"] is None else round(x["db_to_tx_ms"], 1),
        "delta",
        round(x["fill_delta_pips"], 2),
    )
created = {
    "cid-34ea03ffe3fa486ab98e7bad36d45252": "2026-09-22T21:06:03.971050+00:00",
    "cid-8f55b3f86c5d4f2b918f5ee1d56baef0": "2026-09-22T21:06:04.325844+00:00",
    "cid-6d0d82b0369e4f10b370dca4802b0af2": "2026-09-22T21:07:05.411949+00:00",
    "cid-03209f355b264a10b11548a57443d6a7": "2026-09-22T21:08:06.859658+00:00",
    "cid-3ac32014576e44ea986041bc7c85b447": "2026-09-22T21:09:07.918631+00:00",
    "cid-cb964084bab6490b87f5606bebbaee98": "2026-09-22T21:09:08.279056+00:00",
    "cid-eee7fdf92db44f61864421b14ff0ab19": "2026-09-22T21:10:09.771178+00:00",
    "cid-84c40a5c859e4bed8c20118ef9cf5cd7": "2026-09-22T21:11:10.966402+00:00",
    "cid-74595fd264cd484db786041a46582036": "2026-09-22T21:12:11.661646+00:00",
    "cid-ac380f6a32914d59a20e8a2dbc9ee488": "2026-09-22T21:12:12.272048+00:00",
    "cid-683e7c2d6f0a404ea4387efb01892d6d": "2026-09-22T21:13:13.464464+00:00",
    "cid-e6afc545a3d844529fc229dec57cceec": "2026-09-22T21:15:15.216293+00:00",
    "cid-bdb651433a0a4403b6802c46a466d733": "2026-09-22T21:16:16.410522+00:00",
    "cid-b2db42bf9263435983665c6b4df3b4ea": "2026-09-22T21:18:18.583854+00:00",
    "cid-8bde28710212487b9d9df455a32fe8a8": "2026-09-22T21:19:19.766547+00:00",
    "cid-57588c279fc2440d8f4c24abd12c09e2": "2026-09-22T21:25:26.715352+00:00",
    "cid-4fc845893cd149e4b6d7590920e95fac": "2026-09-22T21:29:31.060816+00:00",
    "cid-ba84f573b35b4a16a5b91ff3012bb632": "2026-09-22T21:38:41.072492+00:00",
    "cid-3c886c582acb4550b413eb2f08c125bb": "2026-09-22T21:40:43.331290+00:00",
}
ms = []
print("=== reserve->tx ms ===")
for x in p["cancelled"]:
    t0 = datetime.fromisoformat(created[x["cid"]])
    t1 = datetime.fromisoformat(x["time"].replace("Z", "+00:00"))
    dt = (t1 - t0).total_seconds() * 1000
    ms.append(dt)
    print(x["instrument"], round(dt, 1))
ms.sort()
print("min/med/max", round(ms[0], 1), round(ms[len(ms) // 2], 1), round(ms[-1], 1))
print("cancel stats", p["cancelled_stats"])
print("success stats", p["successful_stats"])
