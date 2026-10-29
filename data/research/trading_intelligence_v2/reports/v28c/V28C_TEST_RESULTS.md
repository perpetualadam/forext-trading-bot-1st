# V2.8C offline tests

2026-10-29, native Windows, Python 3.13, isolated stdlib runners. Final source seal `9a8b0960f0beefe7fb7fbd116cfa320bdfe6b18a2414c936b370a8c3c58445f2`.

**239 tests passed; zero final failures/errors/skips.** No OANDA connection, real credential or LIVE grant. Test logs are retained outside Git in the task scratch directory.

- bounded guard additions: 2 passed; log SHA-256 `86574e8afeb34bd639a57017cac16298b7be870a198ec8859ddbf31ae5b6b71e`.
- bounded: 46 passed; log SHA-256 `4e72ab416fb4c47a3ee27c67f329c06070fe1ba911709417b5adb83fe9a9707a`.
- restricted_transport: 67 passed; log SHA-256 `1e45270c77578e5e4ddc7011dc10f3060ffd76ba937fcf8f424638ebc2a6c4a7`.
- native_isolation: 46 passed; log SHA-256 `eb796f858215e2127921abc94697af94925e3d461e0a5cb84f3873f8361784c6`.
- research_import: 24 passed; log SHA-256 `203a3f7f44efe4adf104f5f48a95a547dc8d06299fd32b652607aa607617784c`.
- pilot_merge: 24 passed; log SHA-256 `06926e632fea02a49ecf4e4af77944e0e758b8a8ffc29aec2df583e6f09f5aa4`.
- year_plan: 30 passed; log SHA-256 `675e22fe5677dd2fb188dc94b0a93d8cd25bd58735f43fb88f7e0e33299e1d55`.

The full bounded integration test completed exactly 106 local HTTPS requests, one credential-provider call, 106 completed journal windows with one charged HTTP attempt apiece, validated per-window hashes and 106 immutable spent markers. All synthetic tokens were absent from persisted session files. A new session identity could not issue authority for that spent catalogue. Synthetic artifacts were refused by the real-provenance importer.

Coverage of the requested 30 categories:

- 1â€“4: exact 106 windows/hash, 105,120 slots, contiguous boundaries, no extra indices, immutable spec copies and fixed GET host/path/parameters.
- 5â€“9: one token entry; no persistence; ordered durable ledger; budget/identity/marker inconsistency refusal; duplicate/spent/pending reservations cannot replay.
- 10â€“11: existing global lock, competing controllers and an actual independent subprocess lock probe; native security tests also race actual workers/controllers.
- 12â€“17: crashes before dispatch, during dispatch and after response; delayed HTTP/cleanup; consumed unknown outcome; second invocation refused and no retry.
- 18â€“20: source-seal mismatch, catalogue/hash mismatch, invalid budget/identity/copy grant and noninteractive LIVE issuance refusal.
- 21â€“22: protected/native archive checks; disk-space failure; actual 256 MiB fixture quota refusal, pending/replacement peak accounting and reserved accounting headroom.
- 23â€“25: actual one-second request spacing, loss of global lease with fencing before token entry, existing rate-delay helper, finite session and request deadlines, slow token entry with a fresh acquisition clock, token timeout without dispatch, immediate stop on bad schema/incomplete/redirect/HTTP 429 and failed parent verification.
- 26â€“27: actual legacy/sibling open/write/substitution probes, junction/hardlink/native ACL regressions; original pilot bytes/modification timestamps, hashes, merged dataset and legacy consumed evidence reverified read-only.
- 28â€“30: fixed GET scope and broker-write rejection; operational import barriers/static checks; existing importer acceptance of an independently reviewed invented bounded-format bundle, rejection of synthetic execution provenance, unchanged research rights/hash/independence regressions.

Commands: `python -I -S -B data/research/trading_intelligence_v2/v26d_run.py` with `--native-bounded-tests`, `--native-bounded-guard-tests`, `--native-v26g-tests`, `--native-rollover-tests`; and v28_run.py/v28a_run.py/v28b_run.py with their corresponding test selectors.

The initial shortened 300-second fixture run stopped before 106 windows and exposed a token-timeout classification bug. A later compatibility regression exposed three dictionary-assumption errors; one synthetic run was intentionally stopped and its worker fencing confirmed before resealing. These were corrected without relaxing LIVE limits or existing tests. The final complete bounded run used a 900-second OFFLINE_TEST fixture limit (LIVE remains 1,800) and took 453.911 seconds for all 46 tests. Prior interrupted fixtures were not reset/reused.

CI YAML parses; the new Ubuntu bounded synthetic job is configured but has not run on GitHub because publication is not authorised. Native Windows ACL/fencing evidence comes from the local tests; no claim of real OANDA connectivity or acquisition success follows from these fixtures.

After the full run, two additional tests instrumented the existing local server with request timestamps and verified global-lease loss. Only the test fixture/test runner/test module changed; sealed production code remained identical. Both additions passed separately; the default CI selector includes all 48 bounded tests. No existing test was skipped or weakened.
