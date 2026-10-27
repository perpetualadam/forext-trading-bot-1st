# V2.5 Test Results

Run python -I -S -B data/research/trading_intelligence_v2/v25_run.py
--v25-tests. Executable tests cover cost formulas and units, BUY/SELL and JPY,
GBP conversion, malformed/stale/future inputs, completed context, frozen policies,
abstention, duplicate votes, clustering/reentry, rejected winners/losers/unknowns,
baseline equivalence, changed portfolio availability, selection isolation,
deterministic hashes and denied network/journal/enablement access.
Negative controls intentionally double a cost expectation or supply lookahead
and require rejection. No financial outcome assertion was weakened.
An initial replay computed the scenarios but failed on a missing report-renderer import while that new module was still being created. The failed-attempt summary was retained in ignored outputs, and the complete pipeline was rerun. Current executed regression and cross-platform results: test_results.json.
Replay provenance, reproducibility and source preservation: verification.json.
Hosted verification is recorded separately after publication; overall CI must
not be described as green when the historical full-suite job fails.

Research only. Production remains NO-GO.
