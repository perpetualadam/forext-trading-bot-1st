# V2.6E test results — 2026-10-28

All final commands below exited **0**, with **0 failures, 0 errors, 0 skips**.
Commands use `python -I -S -B` from the repository root. Windows used Python 3.13;
the Linux run used `/usr/bin/python3` in local Ubuntu. No operational bot was run.

- `data/research/trading_intelligence_v2/v26d_run.py --v26e-tests`: **50**,
  Windows portable; **50**, Linux. Includes all 38 original HTTPS lifecycle tests
  through the new adapter plus 12 source/schema/credential/integration cases.
- `data/research/trading_intelligence_v2/v26d_run.py --native-v26e-tests`: **50**,
  native owner-run Windows with protected archive binding and synthetic sessions.
- `data/research/trading_intelligence_v2/v26d_run.py --tests`: **38**.
- `data/research/trading_intelligence_v2/v26c_run.py --tests`: **71**.
- `data/research/trading_intelligence_v2/v26b_run.py --tests`: **46**.
- `data/research/trading_intelligence_v2/v26_run.py --tests`: **99**.
- `data/research/trading_intelligence_v2/v25_run.py --v25-tests`: **78**.
- `data/research/trading_intelligence_v2/v24_run.py --v24-tests`: **73**.
- `data/research/trading_intelligence_v2/managed_run.py --v23-tests`: **58**.
- `data/research/trading_intelligence_v2/managed_run.py --mtf-tests`: **73**.
- `data/research/trading_intelligence_v2/managed_run.py --tests`: **72**.
- `offline_exposure/run_checks.py`: **57**.
- `data/research/trading_intelligence_v2/v26c_native_check.py --check`: **11 checks**.
- Same native check with `--session-check`: **25 checks**.
- Same native check with `--negative-security-check`: **3 checks**.

The first negative-security invocation exited **1** because its expected
disposable junction fixture was absent, before testing any permission behaviour.
Three empty named synthetic fixtures were created in `research_outputs`, including
the intentionally broad-ACL negative fixture; the unchanged check then passed.
Those fixtures were removed nonrecursively. Existing archive root ACLs, bindings,
historical test assertions and genuine data were not altered.

Coverage: exact non-account EUR_USD/M5/MBA/date/boolean schema; account routes,
orders, trades, closes, alternate hosts and count refused; provider disabled by
default; memory-only post-reservation IPC; no credential persistence/exposure;
TLS trust/hostname failures; HTTP errors/429; no redirect, retry or fallback;
crashes at all seven phases; timeout/restart/race duplicate refusal; total deadline
and worker termination; malformed/oversized/incomplete/echoed responses; observed
9/10 complete-candle results; archive publication, identity and hash verification;
no operational imports or real OANDA request.

GitHub CI adds a dedicated guarded V2.6E job alongside all existing jobs. The
delivery records the exact published SHA and hosted outcome after push; these
local counts are not presented as a substitute for hosted full-suite CI.
