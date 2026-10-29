# V2.8A final decision

LOCAL_PILOT_IMPLEMENTATION_VERIFIED_AWAITING_PUBLICATION_APPROVAL. AUTHENTICATED_EXECUTION_NOT_AUTHORISED. PRODUCTION_NO_GO.

1. Three valid contiguous half-open windows cover 2,016 calendar slots, maxima 1,000 / 1,000 / 16. Actual market candles are not guaranteed; no closures fabricated.
2. Each uses the existing V2.7 single-use architecture via a locally implemented fixed request selector, its own preparation/namespace/grant/journal/claim/result/consumed state. No reusable three-request permit, new downloader/client/authentication system or operational loop.
3. Safeguards preserved; local synthetic end-to-end verification passed for all three profiles. Real execution requires separately approved publication and per-request approval.
4. First exact request: LIVE EUR_USD candle GET, M5/MBA, 2024-08-05 00:00:00Z to 2024-08-08 11:19:59Z inclusive. See V28A_FIRST_REQUEST_APPROVAL.md for command and exact phrases.
5. Planned maximum three independent one-attempt sessions. Current authorised count ZERO. Request one success does not authorise request two; errors/unknown outcomes stop progression.
6. The offline merger reuses V2.8 import checks; only three completed/hash-bound/provenance-reviewed/reconciled batches can combine. It reports gaps and denies strategy evaluation. No real pilot candles have been acquired or merged. Six-pair and frozen-policy requirements remain intact.
7. 253 focused tests passed on final local code, including 36 fixed-profile native synthetic HTTPS tests and 70 existing native activation/rollover regressions.
8. No operational, R.56, frozen-strategy or scheduler source changed. Original consumed sessions and protected market data preserved. New native namespaces contain non-authorising metadata only.
9. Nothing committed or pushed. The complete local source/test/CI/report scope is held for review because it changes LIVE session authority; the task's section 10 requires separate publication approval. Git main remains at the prior verified baseline, with unrelated scheduler changes preserved and unstaged. No CI success is claimed for unpublished code.
10. Before first real GET: approve publication of the concrete reviewed scope, verify published SHA/CI/source seal, then separately approve only the first exact request and truthfully affirm applicable data-use rights. Do not execute any terminal acquisition during this stage.
