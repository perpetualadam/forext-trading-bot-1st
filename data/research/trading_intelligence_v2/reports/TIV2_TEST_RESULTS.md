# Verification commands and evidence

Run synthetic contract tests: `python -I -S -B data/research/trading_intelligence_v2/run.py --tests`. Run full archived study: `python -I -S -B data/research/trading_intelligence_v2/run.py --evaluate`. Run existing coordinator: `python -I -S -B offline_exposure/run_checks.py`. Exact executed local test results are recorded in verification.json after checks; synthetic returns are never profit evidence. Hosted feature-specific CI runs the isolated synthetic suite; it does not download or commit datasets. Existing full CI historical failures remain visible; local checks do not imply overall CI green.

Executed study scenarios=736; deterministic record SHA256 c6dd427475a69132a015b4d78a378238845ae4e0a1dbb5177f19c7009bb7ab72; frozen-input SHA256 c46c6d96feae2d0829247bd4b56c659fc7a4f1d5e21bb75d1c76ce618d793b6e. Full compressed candidate/trade records and per-fold frozen selections are generated under ignored outputs/. Reproduction requires the existing archive and unchanged pinned definitions. Committed compact metrics retain all scenario summaries but no market dataset.

Status: TIV2_OFFLINE_RESEARCH_PARTIALLY_VERIFIED. Production remains NO-GO. All results are hypothetical archived-data replay, never broker fills. The 29-day archive and short OOS windows do not establish statistical significance or live profitability.
