# V2.8B focused offline verification

Final invocations: 223 tests passed; zero failures, errors or skips.

- v28b_run.py --v28b-tests: 30. Exact 106-window/105,120-slot plan, 1,000 maximum/final120, inclusive query ends/half-open coverage, unique deterministic IDs, predecessor chain, no LIVE catalogue scope, non-authorising state, exposure labels, all-completed hash-verified offline merge, missing runs preserved, corrupt/unknown/crashed/repeated/out-of-order sessions refused, rights evidence and pilot-manifest reuse refused, deterministic output, no write endpoint/credential/operational/network access.
- v28a_run.py --v28a-tests: 24. Original three-window planning, boundary/duplicate checks, all-three merge, gaps, identity/grant substitution and ambiguity refusal unchanged.
- v28_run.py --v28-tests: 24. Existing provenance, rights, hashes, identity, precision/price/completion checks and offline barriers.
- v26_run.py --tests: 99. Existing bounded batches, limits, protected/immutable publication and response validation, calendar gaps, duplicate/quote/time checks and research exposure rules.
- v26d_run.py --native-rollover-tests: 46. Synthetic credentials/local HTTPS only; actual native worker isolation/open attacks, global concurrency lock, single-use, predecessor source/identity/claim binding, crash/restart/timeout refusal, no retries or credentials/network before reservation.

The offline year runner initially denied a test's unnecessary import of the network-capable supervisor; the test now checks the fixed request catalogue without importing an execution path. The socket test initially encountered import refusal before socket construction; it now verifies refusal at either point, retaining both audit barriers. No safety check was weakened.

Read-only real-data preservation check: current LIVE source seal and every sealed source byte match published baseline; all original pilot records/hashes/mtimes unchanged; existing merger refactor reproduces the exact 1,440-record hash; saved merged bundle/all assets verify; zero year namespaces or authority created. Operational sources, R.56, frozen strategies and unrelated scheduler work are excluded.

No OANDA contact, real credentials, executable LIVE grants, authenticated requests, strategy replay or optimisation. Offline synthetic success is not evidence that the current LIVE system can authorise the new date range. A dedicated offline CI job is included; exact published-SHA results are reported after publication.
