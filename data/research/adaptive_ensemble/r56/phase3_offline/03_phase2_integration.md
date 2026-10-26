# Phase 2 integration

Phase 2 was not modified. Its Python hashes match the Phase 2 report.

## Reused without change

`collector_session.py` loads these files by path from `r56/phase2_offline/`:

- `account_diagnostics.py` `build`
- `pricing_diagnostics.py` `build`
- `diagnostic_writer.py` `stamp`
- `response_adapter.py`, which those modules load for field extraction and sensitive-literal detection

`stamp` enforces the Phase 2 allowlist and marks each nested record `r56.phase2.1`. The session record is `r56.phase3.1` and sets `phase2_adapters` to `REUSED`.

Missing currency still becomes `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` inside the Phase 2 account record. A pricing document without conversion factors still becomes `HOME_CONVERSION_NOT_VERIFIED`. Quote freshness stays `QUOTE_FRESHNESS_NOT_VERIFIED`. The session adds `GBP_PIP_VALUE_UNVERIFIED`, `STAKE_TO_UNIT_MAPPING_NOT_VERIFIED`, and `FINANCING_NOT_VERIFIED` because these two reads do not establish them.

## Writer path

Phase 2 `write_record` accepts a log directory only under `phase2_offline/synthetic_logs`. Pointing it at the Phase 3 log directory would require editing Phase 2. This phase does not do that.

The session calls `stamp`, then writes the outer allowlisted record with its own exclusive-create writer under `phase3_offline/synthetic_logs`. Extraction, missing-evidence codes, and secret detection stay in Phase 2. The Phase 3 file adds the request result, the session status, and the broker gaps those two endpoints cannot close.

No incompatibility blocked reuse. The pure-data functions are reusable. Only the Phase 2 file destination is intentionally local to Phase 2.
