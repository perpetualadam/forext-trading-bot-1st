# Causal regime evaluation

Fixed before evaluation: abs(MAfast-MAslow)/ATR >=0.5 TREND, <=0.15 RANGE, otherwise UNCERTAIN. Mean-reversion entries require RANGE; others TREND. Spread-only and regime+spread policies require prior completed-bar spread/ATR <=0.25. ATR relative to the past 250 valid ATR median gives HIGH >1.5x, LOW <0.67x, otherwise NORMAL; five-bar price change >=1 ATR tags STRONG momentum. These latter tags are diagnostics, not extra fitted filters. Breakout tags are the existing causal breakout signal; no ADX or redundant feature search. No full-sample fitting; uncertain regimes abstain. Thresholds are fixed hypotheses, not validated production parameters.

- PORTFOLIO / hybrid_research / baseline / protection=False / stress=False: n=557, expectancy R=-0.343697, net USD=-4184.489028, PF=0.396663.
- PORTFOLIO / hybrid_research / baseline / protection=True / stress=False: n=566, expectancy R=-0.345531, net USD=-4267.116475, PF=0.385077.
- PORTFOLIO / selected / baseline / protection=False / stress=False: n=0, expectancy R=UNDEFINED, net USD=0.000000, PF=UNDEFINED.
- PORTFOLIO / selected / baseline / protection=True / stress=False: n=0, expectancy R=UNDEFINED, net USD=0.000000, PF=UNDEFINED.

Adding regime to spread filtering increases sample R expectancy in 11 of 29 comparable pair/strategy cells; this is an exploratory cell count with dependent trades, not a significance claim. Per-pair comparisons are in study_summary.json; matched accepted/rejected baseline trade outcomes are in outputs/metrics.json. Actual filtered replays change trade availability and capital, so matched-entry outcomes are reported separately; rejected signals are not assigned fabricated trade outcomes. No claim that this beats the actual live selector is supported by shadow-rule results.

Status: TIV2_OFFLINE_RESEARCH_PARTIALLY_VERIFIED. Production remains NO-GO. All results are hypothetical archived-data replay, never broker fills. The 29-day archive and short OOS windows do not establish statistical significance or live profitability.
