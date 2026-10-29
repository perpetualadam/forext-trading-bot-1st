# V2.8A focused offline verification

Final local implementation: 253 tests passed; zero failures/errors/skips in final invocations.

- v28a_run.py --v28a-tests: 24. Exact three-window planning; half-open boundaries; unique IDs; frozen/copy-isolated specs; all-three merge; edge/cross-boundary missing runs; duplicates/reordering; source/session/grant/raw tampering; consumed state/one-attempt requirement; crash/timeout/OUTCOME_UNKNOWN refusal; no automatic progression.
- v28_run.py --v28-tests: 24. Existing importer rights/provenance/identity/hash/price/time/completion checks; active network, credential and operational-write barriers.
- v26_run.py --tests: 99. Existing bounded batching/rate controls, exact ranges, archive integrity, timestamps, missing components, JPY/pip conventions, decimal lexemes, duplicates and gaps/weekends.
- v26d_run.py --native-rollover-tests: 46 (74.418 seconds). Actual worker opens, junctions/hardlinks, namespace isolation, durable reservation/global lock, concurrency, single-use, crashes, ambiguous outcomes, legacy compatibility and no credential/network before reservation.
- v26d_run.py --native-activation-tests: 24 (45.133 seconds). Terminal attestations, hidden token entry, slow input/fresh acquisition deadline, timeout fencing, no retries/redirects/write routes and synthetic HTTPS.
- v26d_run.py --native-pilot-tests --pilot-window=1, 2 and 3: 12 each, 36 total. Actual selected-profile supervisor/child/loopback HTTPS, exact other-window refusal, no repeat, no automatic next grant, missing preparation refusal, fixed selectors, cross-profile capability refusal before credentials, predecessor UNKNOWN/pending/corrupt archive refusal, successful predecessor verification still conferring no authority.

Native tests used the established scratch ci-venv interpreter, disposable synthetic fixtures and local HTTPS only. No real credentials, LIVE grants or OANDA calls. Synthetic bundles marked with real-format fields are invented test inputs and confer no authentic provenance or executable authority.

An initial test helper referenced the wrong fixture-module alias and was corrected. One regression run overlapped an implementation source-seal refresh and returned OUTCOME_UNKNOWN for its synthetic slow-input case; the entire native suite was rerun after source freeze and passed without weakening the test or deadline. An initial interpreter path was corrected to the existing scratch venv. Final source seal is fixed and verified.

Prior consumed evidence checked read-only. Dedicated offline pilot CI job is prepared locally. Nothing committed/pushed; no exact-SHA CI result is claimed for the unpublished implementation. Separate publication approval required because request-profile admission changes LIVE authority.
