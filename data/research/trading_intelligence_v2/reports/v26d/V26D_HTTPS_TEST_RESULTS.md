# Tests and exact entry points

Existing Python/OpenSSL only; no package installation. Commands run with isolated
stdlib entry points, no unrestricted application imports. All final runners exit 0.

## Actual HTTPS

- Windows: `python -I -S -B data/research/trading_intelligence_v2/v26d_run.py --tests`:
  **38 passed**, 0 failures/errors/skips (26.654 s final run).
- Ubuntu Python 3.12: the same entry point via existing WSL `/usr/bin/python3`:
  **38 passed**, 0 failures/errors/skips. Private absolute checkout prefix omitted.
- Windows archive owner: `python -I -S -B data/research/trading_intelligence_v2/v26d_run.py --native-tests`:
  **38 passed**, 0 failures/errors/skips (final run recorded locally).

These use real TCP/TLS, a loopback-only ephemeral listener and generated temporary
EC certificate/key. Certificate chain and hostname verification remain enabled.
Rejection tests require one observed TLS connection and the verification error,
not merely any local refusal. Connection refusal holds an unlistening bound port.
Test-only keys/config/certificates are removed after each suite, never staged.

Cases cover valid completed MBA, nine candles, incomplete candles, untrusted
certificate, hostname mismatch, connection refusal, TLS/header/body delays,
declared/streamed oversize, truncated body, 401/403/404/429/500, redirect, malformed
JSON, invalid schema, credential echo, disabled entry/provider ordering/redaction,
missing permission, two-process HTTPS race, all seven crash points, restart
refusal, hash verification and non-fixture network/production-state barriers.
Every completed attempt/timeout/crash is retried only as a **refusal assertion**:
the second invocation cannot call the provider or create another network request.

## Required regressions

- `python -I -S -B data/research/trading_intelligence_v2/v26c_run.py --tests`: 71.
- `python -I -S -B data/research/trading_intelligence_v2/v26b_run.py --tests`: 46.
- `python -I -S -B data/research/trading_intelligence_v2/v26_run.py --tests`: 99.
- `python -I -S -B data/research/trading_intelligence_v2/v25_run.py --v25-tests`: 78.
- `python -I -S -B data/research/trading_intelligence_v2/v24_run.py --v24-tests`: 73.
- `python -I -S -B data/research/trading_intelligence_v2/run.py --v23-tests`: 58.
- `python -I -S -B data/research/trading_intelligence_v2/run.py --mtf-tests`: 73.
- `python -I -S -B data/research/trading_intelligence_v2/run.py --tests`: 72.
- `python -I -S -B offline_exposure/run_checks.py`: 57.

Windows regressions: **627 passed, 0 failures, 0 errors, 0 skips**.
Ubuntu also passes the preserved C suite: **71 passed**, exit 0, no failures/errors/skips. The final V2.6
rerun supersedes its development error below. Native C archive and session checks
also pass, recorded in STORAGE_AND_SECURITY. No unrestricted full-suite local run.

## Development failures (all resolved before publication)

Four initial 36-case Windows runs each had **22 failures, 0 errors, 0 skips**:
empty child environment caused Winsock 10106 before connection. Adding only the
fixed OS bootstrap directory resolved it; no network destination was broadened.
Then 36 passed, followed by tightened 37-case runs passing on all three paths. A final
post-send dispatch stall and provider-refusal assertions extend the suite to 38.

Initial native 37-case run: **0 failures, 32 errors, 0 skips**. Python 3.13 mkdtemp
applied a different DACL; the archive correctly refused. Newly created native
test directories now inherit owner/SYSTEM permissions. Existing ACLs unchanged.

One V2.6 99-case regression run had **0 failures, 1 error, 0 skips**: its injected
reply lacks HTTP framing metadata. The shared transport now supports that old
fixture protocol; the unchanged 99 tests and real incomplete-body tests pass.
No tests/assertions were removed or weakened to hide these failures.

CI adds C's isolated 71-case job and D's 38-case real-loopback job, leaving the
full historical suite intact. Hosted outcomes are reported after the exact SHA
is published; local success alone is not overall green CI.
