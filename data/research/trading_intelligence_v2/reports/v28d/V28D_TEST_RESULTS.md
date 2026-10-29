# V2.8D tests

**285 focused tests passed; zero failures, errors or skips.** Final local source seal: `9511b6a2d834510080f73275da3d64b8951185e0a841487723c56df2a18434d4`.
Native Windows/Python 3.13; stdlib isolated audit-barrier runners, synthetic credentials and loopback HTTPS only.

- research: 21 passed; log SHA-256 `0f52ce5985ebe785ce0ab9664272f60570b2077cf5d436e0cbfe93e221b17510`.
- diagnostics: 25 passed; log SHA-256 `8bd32e48dc16e3f21366f593be63838161b960eade457cff9af278f4f0639b4b`.
- bounded: 48 passed; log SHA-256 `8af028e580bb9c1c30289bb09c90221a34d25e223c7f2905ce2b543fbb1139e7`.
- security: 67 passed; log SHA-256 `ba650979ac0e030a80bd4ff91c60333dcca003968a2779eb238491fafe29b711`.
- isolation: 46 passed; log SHA-256 `b8cf997798eac53a5a5a8596c23881c718c52a59f3eefed87a86da3e2cfb66b1`.
- v28: 24 passed; log SHA-256 `ecda2460a877393ce2c4467aa2609c2352e16a68eeb90d442901f94e9d228a76`.
- v28a: 24 passed; log SHA-256 `d7a6f782273e3a42487409c680613eac23e143b8df8a8804dd7d7ca858e38162`.
- v28b: 30 passed; log SHA-256 `c2d746c27340ee436672b30f6b26378cbb2006df5dad54bc87b81551d4836bba`.

Research tests cover all 39 identities and actual OUTCOME_UNKNOWN parent semantics, exact prefix, source/session/manifest/right/hash corruption, duplicate/ordering/range checks inherited from the unchanged importer, ambiguity preservation and independence refusal. The 66 remaining specifications are byte-identical in canonical request encoding to original windows 41â€“106, with no reserved/unknown entries admitted.

The 25 diagnostic tests cover actual local connect refusal and typed connect timeout, stubbed DNS refusal with no external socket, TLS verification rejection, HTTP 403, delayed headers/body, truncation, bad candle schema, synthetic archive failure, unexpected worker exit, per-window/aggregate watchdogs, transmission termination, corrupt accounting, lock loss, unknown exception/secret-response redaction, tampered diagnostic hashes, interrupted publication, actual independent-process diagnostic reopening and refusal to overwrite a partial derivative commit.

Deadline races report the observed watchdog deadline and last stage when the worker is fenced before it can emit a typed timeout. Tests accept that distinction rather than inventing a network cause. Every failure path keeps claimed/spent evidence, at most one HTTP attempt in failure fixtures, no automatic retry and refusal on a second invocation. No existing safety test was weakened or skipped.

Existing 48 bounded, 67 restricted-network and 46 native isolation regressions verify one token for 106 exact synthetic requests, immutable catalogue/source and budgets, existing actual-file-open/junction/hardlink/ACL isolation, process fencing, no broker writes and no operational imports. Existing importer/pilot/year tests retain rights, provenance, complete-parent and independence gates.

Real archive checks are additional to the 285 tests: all 126 consumed-session files matched pre-investigation SHA-256/size/mtime snapshots, all 39 raw/validated/manifest sets were revalidated, the new gzip derivative was atomically committed in a unique protected directory and a fresh process remerged original inputs and proved identical records/hashes. The archived previous pilot/September/merged/legacy evidence is rechecked separately. No original records are repaired or overwritten.

Commands use v26d_run.py with --native-v28d-diagnostic-tests, --native-bounded-tests, --native-v26g-tests, --native-rollover-tests; v28d_research_run.py; and v28_run.py/v28a_run.py/v28b_run.py with their fixed selectors. Logs remain in task scratch outside Git. The CI workflow parses and adds only synthetic/offline steps; GitHub CI has not run for these unpublished changes.

Physical media that cannot accept writes cannot guarantee a final diagnostic file. Claimed/pending authority remains spent; no alternate storage or retry bypass is introduced. The interrupted-publication test explicitly verifies this fail-closed limitation.
