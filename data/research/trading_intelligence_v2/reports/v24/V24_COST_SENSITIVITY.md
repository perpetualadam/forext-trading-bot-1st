# V2.4 Cost Sensitivity

sensitivity.json contains 54 aggregate scenarios and both fold summaries:
all six unchanged strategies as M5 six-pair portfolios; trend also M15/H1/H4.
No strategy optimisation, parameter fitting or independent evaluation claim.
A: midpoint theoretical, no spread/slip/commission. B: observed bid/ask only.
C: B + hypothetical 0.2 pip per fill. D: C + hypothetical 3 account units/100k
base units per side. E: 2x observed quoted half-width, 1 pip slip, commission3.
F: same observed spreads + 0.2 pip + documented US7/100k side comparator, not UK.

Features and signals use original candles; execution quote stress changes only
bid/ask fills, triggers, conversion and capital path. Replay recomputes sizing,
eligibility and exits. Hashes identify changed entry/exit paths. Even a matching
path can resize; these comparisons are not purely additive fixed-trade debits.
Each fold starts separately at 10,000; drawdown is reported per fold and maximum
fold drawdown, never a fabricated continuous two-fold equity curve.

Break-even cost is gross account P/L / trade count on THAT realised path; negative
means no positive cost can rescue it. Not a recommendation, calibrated rate or
root of a rerun equilibrium. Financing is retained only as the labelled existing
UTC-date assumption; no broker historical funding inputs are available.

M5 trend full-replay results (USD; gross / net / trades / max fold drawdown):
- A_MID_THEORETICAL: -377.516186 / -377.516186 / 750 / 613.334370; baseline path matches=False.
- B_OBSERVED_ONLY: -13.288709 / -4210.742405 / 807 / 2391.279123; baseline path matches=False.
- C_OBSERVED_SLIP_02: -115.493062 / -5215.846769 / 828 / 2848.304993; baseline path matches=False.
- D_HYPOTHETICAL_3_PER_100K_SIDE: -108.118651 / -6204.763853 / 829 / 3385.785489; baseline path matches=True.
- E_STRESS_2X_SPREAD_1_PIP_SIDE: 413.062049 / -15947.891039 / 1640 / 8483.189055; baseline path matches=False.
- F_US_CORE_7_COMPARATOR_NOT_UK_PLAN: -110.227224 / -7171.256312 / 830 / 3939.897527; baseline path matches=False.


Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.
