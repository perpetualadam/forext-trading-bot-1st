# Adaptive selection

Candidate entry timeframes M5/M15/H1/H4 and existing strategy names use the same execution model. A train-only map conditions on causal M5 regime and volatility; entry-timeframe signals must be newly completed. Each context needs >=10 closed training trades and positive mean R minus 1.96*standard-error score. Highest positive score wins with deterministic policy-key tie break, not trade count or highest cash return. This penalty is a selection heuristic, not a valid significance interval. A pair-level validation replay then needs >=20 trades and a positive penalized score; otherwise its entire map abstains. Maps are immutable during test. No recent test outcomes update routing. Adaptive fits use independent timeframe candidates only; confirmation policies are separate fixed comparisons, not additionally searched.

- Fold 1: train rules=0; validation-approved rules=0.
- Fold 2: train rules=0; validation-approved rules=0.

- PORTFOLIO / ADAPTIVE / ADAPTIVE: trades=0, R expectancy=UNDEFINED, PF=UNDEFINED, net USD=0.000000, net return=0.000000.
- PORTFOLIO / ADAPTIVE / ADAPTIVE: trades=0, R expectancy=UNDEFINED, PF=UNDEFINED, net USD=0.000000, net return=0.000000.
- PORTFOLIO / ADAPTIVE / ADAPTIVE: trades=0, R expectancy=UNDEFINED, PF=UNDEFINED, net USD=0.000000, net return=0.000000.
- PORTFOLIO / ADAPTIVE / ADAPTIVE: trades=0, R expectancy=UNDEFINED, PF=UNDEFINED, net USD=0.000000, net return=0.000000.

Actual selected context rules, holding choices and approval/fallback status are in selected_policies.json. An all-abstain model is not labelled profitable or a successful active selector.

Classification: TIV22_MTF_RESEARCH_PARTIALLY_VERIFIED. Production NO-GO. Archived-market replay, not broker fills. This 29-day archive was already examined during TIV2; these are chronologically out-of-fit comparisons, not a fresh independently untouched dataset. No reliable profitability or operational advantage is established.
