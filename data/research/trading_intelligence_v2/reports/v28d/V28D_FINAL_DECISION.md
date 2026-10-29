# V2.8D final decision

**TIV28D_PARTIAL_ARCHIVE_AND_DIAGNOSTICS_VERIFIED** — offline only.

1. All 39 completed batches independently pass session/index/spec/source/catalogue, one-attempt accounting, raw/validated/manifest hashes, candle completion/OHLC/precision/order and duplicate/overlap checks. Original SHA-256 and modification times are unchanged.
2. The partial dataset was atomically saved in a fresh protected research_outputs directory and independently reopened/recomputed in a separate process.
3. Count 27,213; canonical records SHA-256 `81b006a153237ac42dabbbd817a5e56b80493cb82b89bd0db4705a207a64a8a9`. Stored gzip SHA-256 `007d85b7c95176a830ddeddf799c58f29401960773c924754f25a2a1bc174ab0`. Exact path is in V28D_PARTIAL_ARCHIVE.md; no market data is placed in Git.
4. Window 40 and parent remain OUTCOME_UNKNOWN, with consumed authority and all 40 spent reservations preserved. No retry or reinterpretation as unused/confirmed failure.
5. Fixed reason/stage diagnostics are added to the existing exchange, worker and supervisor, atomically published via the existing Archive and hash-linked from result.json. No new network stack, archive or journal.
6. Future observed failure classes can be reported with bounded metadata; unsupported causes stay UNKNOWN_FAILURE. No raw exception strings, credential/header/IPC/body/environment/configuration/account data is persisted. The original window-40 cause remains unknown; diagnostics are not retroactively added to it.
7. No diagnostic or failure path grants permission to retry. Claimed authority, marker accounting, pending-file refusal, global locking and fencing remain. Failed final writes never create an alternate authority/store.
8. Remaining catalogue is exactly original windows 41–106, 66 entries and 65,120 calendar slots, from 2025-01-17T21:20:00Z to 2025-09-01T00:00:00Z exclusive. Exact original specification bytes/hashes are retained; windows 1–40 excluded. It is non-authorising, not activated and not supported by the current hardcoded 106-window runtime.
9. No operational trading, R.56 or frozen strategy files changed. The three unrelated existing scheduler modifications and local runtime selector are excluded. Scheduler remains enabled.
10. 285 focused tests pass, plus real archive/saved-derivative/independent-process verification. No real credential or authenticated OANDA request was used.
11. Nothing committed or pushed. Non-authorising research changes are eligible under category A; this integrated local package remains uncommitted because worker/source-seal and shared CI/test support require category-B approval. No force push.
12. Separate publication approval is required for the bounded supervisor, diagnostic encoder, transport hooks, worker, archive accounting, unused/pending guards and source seal, with their direct test/runner/CI support. V28D_SHA256.json separates categories and exact paths; V28D_SOURCE.diff captures the proposal against 4c99b5f7b38eecb8872947ce395499bce516487c.
13. Before another acquisition: review/publish diagnostic changes; separately review compatible immutable 66-window admission support and its source seal (not implemented/activated here); bind rights to the new catalogue; create a new separately approved proposal/namespace/authority with fresh terminal attestations/token. Never reuse the consumed session or include window 40. No new grant or session proposal was created in this task.
14. The private partial dataset supports exploratory diagnostics and later existing bid/ask cost accounting. It is previously examined/independence-unverified, retains unknown weekend/holiday/missing periods, is not complete 12-month history and establishes no profitability. No strategy optimisation/tournament was run.

The diagnostic source seal changed locally to 9511b6a2d834510080f73275da3d64b8951185e0a841487723c56df2a18434d4. The old consumed selector retains its original source and is stale; it was not silently activated or rewritten.

**No authenticated OANDA requests. No replay of window 40. No trading. Production remains NO-GO.**
