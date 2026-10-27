# Portfolio risk

- PORTFOLIO / hybrid_research / baseline / protection=False / stress=False: n=557, expectancy R=-0.343697, net USD=-4184.489028, PF=0.396663.
- PORTFOLIO / hybrid_research / baseline / protection=False / stress=True: n=581, expectancy R=-0.412372, net USD=-5068.136898, PF=0.319608.
- PORTFOLIO / hybrid_research / baseline / protection=True / stress=False: n=566, expectancy R=-0.345531, net USD=-4267.116475, PF=0.385077.
- PORTFOLIO / hybrid_research / baseline / protection=True / stress=True: n=588, expectancy R=-0.412023, net USD=-5118.861950, PF=0.312783.
- PORTFOLIO / selected / baseline / protection=False / stress=False: n=0, expectancy R=UNDEFINED, net USD=0.000000, PF=UNDEFINED.
- PORTFOLIO / selected / baseline / protection=False / stress=True: n=0, expectancy R=UNDEFINED, net USD=0.000000, PF=UNDEFINED.
- PORTFOLIO / selected / baseline / protection=True / stress=False: n=0, expectancy R=UNDEFINED, net USD=0.000000, PF=UNDEFINED.
- PORTFOLIO / selected / baseline / protection=True / stress=True: n=0, expectancy R=UNDEFINED, net USD=0.000000, PF=UNDEFINED.

Portfolio replay orders simultaneous candidates alphabetically for reproducibility; this introduces a declared allocation priority. Independent pair returns are never simply summed to represent a financed portfolio. USD directions counted separately; opposing directions do not net away gross risk. Conservative bid/ask account conversions, cash-risk caps, maximum slots, margin and MTM drawdown enforced. USD slot concentration is a coarse correlation control, not a fitted covariance/stress model. Broker observations, quarantine and unknown live exposure are absent, and never treated as simulated managed positions. No live portfolio risk totals inferred. Concentration diagnostics by pair/regime/session and MTM drawdown per run are recorded.

Status: TIV2_OFFLINE_RESEARCH_PARTIALLY_VERIFIED. Production remains NO-GO. All results are hypothetical archived-data replay, never broker fills. The 29-day archive and short OOS windows do not establish statistical significance or live profitability.
