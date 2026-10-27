# V2.5 Entry Quality

Pre-entry cohorts on actually executed M5 observed-only trend entries:
- cost_target=LE_025: 807 trades, net -4210.742405, gross -13.288709 USD; net/trade -5.217772.
- regime=RANGE: 153 trades, net -594.740293, gross 163.177028 USD; net/trade -3.887191.
- regime=TREND: 445 trades, net -2816.739588, gross -407.561227 USD; net/trade -6.329752.
- regime=UNCERTAIN: 209 trades, net -799.262524, gross 231.095490 USD; net/trade -3.824223.
- session=ASIA_UTC: 278 trades, net -1495.259940, gross 214.730968 USD; net/trade -5.378633.
- session=EUROPE_UTC: 199 trades, net -1052.573832, gross -132.555104 USD; net/trade -5.289316.
- session=OVERLAP_UTC: 158 trades, net -520.282996, gross 98.702243 USD; net/trade -3.292930.
- session=US_UTC: 172 trades, net -1142.625636, gross -194.166816 USD; net/trade -6.643172.
- spread_atr=GT_025: 724 trades, net -4025.564384, gross -16.531211 USD; net/trade -5.560172.
- spread_atr=LE_025: 83 trades, net -185.178021, gross 3.242502 USD; net/trade -2.231060.
- volatility=HIGH: 227 trades, net -1042.390904, gross -235.434135 USD; net/trade -4.592030.
- volatility=LOW: 125 trades, net -647.304450, gross 277.094680 USD; net/trade -5.178436.
- volatility=NORMAL: 455 trades, net -2521.047051, gross -54.949254 USD; net/trade -5.540763.

These overlapping cohorts describe conditional sample outcomes, not causal
causes or a trained classifier. Costs, directional movement, exits and capital
path interact. Weak momentum, low/high volatility and context conflict are
recorded causal metadata; no probability or profitable condition was inferred.
Complete per-fold cohort records: entry_quality.json; per-entry cost inputs and
counterfactuals: ignored outputs/v25/decision_records.jsonl.gz.

Every policy candidate is paired by instrument/time/side to the baseline action.
Executed baseline trades retain their full baseline trade record. No baseline
trade means outcome UNKNOWN_UNEXECUTED_BASELINE, never zero or assumed loser.
Rejected winners and losers are both counted. Matching baseline outcomes cannot
measure opportunity cost for trades baseline never executed.

Research only. Production remains NO-GO.
