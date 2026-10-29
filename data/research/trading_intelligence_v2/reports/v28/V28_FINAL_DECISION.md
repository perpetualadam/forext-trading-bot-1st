# V2.8 final decision

OFFLINE_PREPARATION_COMPLETE; EXPANDED_ACQUISITION_NOT_AUTHORISED; INDEPENDENT_EVALUATION_BLOCKED; PRODUCTION_NO_GO.

1. Genuine OANDA data available: ten EUR_USD M5 candles (50-minute request), connectivity-only. No new history acquired in V2.8.
2. Additional required: at least 12 months across all six pairs, preferably 24 months; approximately 449,280 or 900,288 weekday-grid candles respectively, subject to session/holiday verification. No eligible independent rows currently available.
3. Bounded plan: three-window EUR_USD week pilot, quality review, then one-pair longer coverage, then remaining five; 636 total 12-month or 1,266 total 24-month 1,000-slot windows. Detailed assumptions in V28_DATA_ACQUISITION_PLAN.md.
4. Independence: current sample is examined and overlaps known development exposure. Candidate older periods are not certified untouched; research-history and first-access review required.
5. Positive net-expectancy strategies: not established.
6. Higher-timeframe improvement: not established.
7. Profit-protection improvement: not established.
8. Supported weaknesses: no causal strategy weakness established by this sample; observed quote spread exists, but performance attribution requires cost-aware matched-period evaluation.
9. Validated improvement: offline provenance-aware ingestion is tested; no trading improvement is validated for promotion.
10. Next practical step: separately approve exact pilot bounds, maximum attempts and applicable private research/derived-use permissions, review compatibility of the existing exact-scope admission mechanism, then acquire and review only that pilot before considering expansion.

No executable authority created, no real credentials read, no OANDA request sent, no consumed session reset, no trading/strategy/R.56/scheduler code changed. Existing generic importer, source seal, frozen policies and operational gates are preserved. Research-only code/tests/CI/reports may be published per user instruction; unrelated local scheduler state is excluded.
