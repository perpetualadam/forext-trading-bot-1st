# Account snapshot trace

SOURCE-REVIEWED. `current_equity` returns broker NAV when present, otherwise the equity curve, otherwise `Config.BASE_BALANCE` (default 10000). The old shared path used that fallback when `account_present` was false and then sized from it. The production tail also sizes from `current_equity` and reads `last_account_summary` for NAV reporting. That summary is a cache from a broker fetch. It has no freshness gate and no identity gate before sizing.

No production account snapshot was fetched in R.15. Production identity and freshness remain NOT_EVALUATED.
