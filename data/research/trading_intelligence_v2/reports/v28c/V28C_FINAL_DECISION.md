# V2.8C final decision

**TIV28C_BOUNDED_ACQUISITION_VERIFIED_OFFLINE**

1. One separately authorised session can execute all 106 fixed requests with one token entry: demonstrated against local synthetic HTTPS.
2. The unchanged catalogue is hash-checked and source-sealed; real authority additionally binds a fresh parent namespace, directory identity and rights hash.
3. A reserved/crashed/ambiguous window cannot be repeated automatically. Immutable spent markers survive process exit. This catalogue cannot resume after any reservation; a reviewed remaining-scope catalogue and new approval/token would be required.
4. Maximum 106 budget reservations, each index at most once, are durably enforced before dispatch. Ambiguous reservations count against the budget even if HTTP was not observed.
5. 256 MiB peak artifact cap (including pending files/markers), publication free-space checks and conservative one-second rate pacing are implemented; 1 MiB is reserved for accounting.
6. A failed/unknown request, validation/hash/accounting/storage/lock/source/deadline failure, crash or interrupt ends the acquisition; no skip/retry/fallback.
7. Original consumed/pilot evidence and the saved 1,440-candle research bundle remain unchanged; legacy OUTCOME_UNKNOWN is preserved. The enabled scheduler remains Ready, last result 0; its three pre-existing changed files are excluded.
8. Real credentials are terminal-only and memory-only, sent once by anonymous pipe, never persisted or loaded from production configuration. Python heap zeroisation is not claimed.
9. Only fixed candle GETs are exposed. No order/trade/position-close route or operational bot startup is added. R.56, frozen policies and operational trading files are unchanged.
10. 239 focused tests passed (48 bounded: 46 full-suite plus two additional guard checks, 67 restricted transport, 46 native isolation, 24 importer, 24 pilot, 30 yearly plan), with zero final failures/errors/skips.
11. Proposed scope: 15 implementation/test/CI/source-seal files, five reports, one exact diff and one manifest (22 files). See V28C_SHA256.json for every path and hash; old local proposals, scheduler edits and protected market/session data are excluded.
12. All 22 files require separate publication approval. Nothing is staged, committed or pushed; main remains 52568b3e2a69c36296f7b3fe2fc502b9c5a290eb. No new GitHub CI result is claimed.
13. A real 106-request session requires separate explicit acquisition approval, published source binding, expanded catalogue-specific rights evidence, protected capacity/identity/global-lock checks, a newly prepared non-authorising identity and exact terminal attestations. Pilot rights are not silently expanded. No real year namespace, executable grant or preparation file was created.
14. Exact next action: review V28C_SOURCE.diff, the SHA-256 manifest and approval report; approve publication separately if acceptable. Do not activate acquisition. After any future publication, verify CI and prepare a newly source-bound proposal under separate authority.

No holdout independence, profitability, real connectivity or acquisition completeness is established by synthetic tests. Existing importer rights/independence gates and unverified market-gap classifications remain. Acquisition does not authorise research optimisation or production trading.

**PRODUCTION TRADING REMAINS NO-GO.**
