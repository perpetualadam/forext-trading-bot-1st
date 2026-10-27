# Walk-forward results

- Fold 1: train ['2026-09-01T00:00:00+00:00', '2026-09-21T03:30:00+00:00']; validation ['2026-09-21T03:30:00+00:00', '2026-09-25T09:20:00+00:00']; test ['2026-09-25T09:20:00+00:00', '2026-10-01T15:15:00+00:00'].
- Fold 2: train ['2026-09-01T00:00:00+00:00', '2026-09-25T09:20:00+00:00']; validation ['2026-09-25T09:20:00+00:00', '2026-10-01T15:15:00+00:00']; test ['2026-10-01T15:15:00+00:00', '2026-10-09T07:05:00+00:00'].

Half-open chronological intervals. Two expanding training windows; nonoverlapping OOS tests; fold-one test may become fold-two validation only after its time. Full causal history is permitted for warm-up, but signals/fits never see future rows. Each simulation starts flat and closes at its partition boundary. Selection requires >=20 train and >=20 validation trades and positive R expectancy in both; largest validation R expectancy wins with alphabetical ties. No eligible strategy => abstain. Train-only nonnegative expectancy weights feed the shadow hybrid. Frozen selections are persisted before each OOS run. Final 20% was not used to tune parameters in this study; this is not an assertion that the archive was never examined by prior researchers.

- Fold 1 EUR_USD: selected ABSTAIN.
- Fold 1 GBP_USD: selected ABSTAIN.
- Fold 1 USD_JPY: selected ABSTAIN.
- Fold 1 AUD_USD: selected ABSTAIN.
- Fold 1 USD_CAD: selected ABSTAIN.
- Fold 1 USD_CHF: selected ABSTAIN.
- Fold 2 EUR_USD: selected ABSTAIN.
- Fold 2 GBP_USD: selected ABSTAIN.
- Fold 2 USD_JPY: selected ABSTAIN.
- Fold 2 AUD_USD: selected ABSTAIN.
- Fold 2 USD_CAD: selected ABSTAIN.
- Fold 2 USD_CHF: selected ABSTAIN.

Status: TIV2_OFFLINE_RESEARCH_PARTIALLY_VERIFIED. Production remains NO-GO. All results are hypothetical archived-data replay, never broker fills. The 29-day archive and short OOS windows do not establish statistical significance or live profitability.
