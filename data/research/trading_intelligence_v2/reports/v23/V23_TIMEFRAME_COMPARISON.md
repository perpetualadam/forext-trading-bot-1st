# Unchanged multi-timeframe replay

- PORTFOLIO/PORTFOLIO_M5/trend: n=829, gross R=-0.004168, net R=-0.370469, cost class=NEGATIVE_GROSS_AND_COST_DRAG.
- PORTFOLIO/PORTFOLIO_M15/trend: n=578, gross R=0.005745, net R=-0.230698, cost class=POSITIVE_GROSS_OVERWHELMED_BY_COSTS.
- PORTFOLIO/PORTFOLIO_H1/trend: n=151, gross R=-0.021879, net R=-0.141507, cost class=NEGATIVE_GROSS_AND_COST_DRAG.
- PORTFOLIO/PORTFOLIO_H4/trend: n=43, gross R=-0.057325, net R=-0.109376, cost class=NEGATIVE_GROSS_AND_COST_DRAG.

These are financed six-pair fixed-trend controls with shared capital/risk constraints, not sums of standalone pair returns. Compare R expectancy, gross-positive realised outcomes, per-trade costs and holding durations alongside total P/L. Different frequencies/holding limits are part of the unchanged policy; smaller cumulative losses do not establish better predictive accuracy. confirmation_diagnosis.json groups baseline executed trades by agreeing/opposing/WAIT/missing H1/H4 context and retains their realised outcomes. It measures which baseline executed winners/losers a condition would reject, not outcomes of all unexecuted candidates. Actual confirmation replays are reported separately because altered capital and availability affect later opportunities. H4 sparse/zero warm-up cells remain data-limited; no independent timeframe conclusion is available.

TIV23_RESEARCH_PARTIALLY_VERIFIED. Production remains NO-GO. No new independent archive was acquired. Existing data is PREVIOUSLY_EXAMINED; these diagnostics are exploratory, not independent validation, policy optimisation or proof of future profitability.
