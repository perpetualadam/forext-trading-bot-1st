# V2.8 focused offline verification

All commands use python -I -S -B; no authenticated requests or real credentials. New test runner clears environment and denies sockets, subprocesses, operational imports, credential files, archive writes and writes outside disposable test workspace. Synthetic bundles cannot create LIVE authority. No broader infrastructure audit was repeated.

- v28_run.py --v28-tests: 24 passed. Hash/derivative tampering, source/identity/session/range binding, provider rights, false synthetic provenance, endpoint/method parameters, crossed quotes, ordering, incomplete candles, known connectivity non-independence, reviewed hash, deterministic conversion and active offline barriers.
- v26_run.py --tests: 99 passed. Existing OANDA timestamps, decimal lexemes, bid/ask, JPY, immutable storage, gaps/weekends, bounded batches, rate limits, no broker writes, data exposure and walk-forward purge.
- run.py --mtf-tests: 73 passed. Completed M15/H1/H4 aggregation, DST, causal availability, training/validation separation and leakage negatives.
- v24_run.py --v24-tests: 73 passed. Costs, conversion, slippage, commissions, protection timing, independent accounting and deterministic replay.
- v25_run.py --v25-tests: 78 passed. Frozen decision filters, exact votes, cost/portfolio constraints, validation vetoes and untouched-test separation.

Total: 347 passed, zero failures/errors/skips in the final suite invocations. An initial new-suite fixture imported the network-capable fixture module and was correctly denied by the audit barrier; replaced with local invented candle construction without relaxing the barrier. An initial v22_run.py invocation named a nonexistent runner; the correct existing run.py --mtf-tests passed. Neither was a source/safety regression.

Actual ten-candle archive revalidated read-only, both recorded hashes matched, data-quality PASS, original session evidence unchanged. No bulk history, performance replay or new rights confirmation was fabricated. CI includes a dedicated offline V2.8 job; exact publication-SHA results must be checked after push.
