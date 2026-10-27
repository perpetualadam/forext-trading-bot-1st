# Offline verification

All commands use existing Python installations; no packages installed. Prefix
research entry points below with `data/research/trading_intelligence_v2/`.

## Final checks

- Windows: `python -I -S -B data/research/trading_intelligence_v2/v26c_run.py --tests`: **71 passed,
  0 failures, 0 errors, 0 skips**, 29.807 s.
- Existing Ubuntu Python: same command via `wsl -d Ubuntu --exec /usr/bin/python3`
  and the corresponding /mnt/c source path; **71 passed, 0 failures, 0 errors,
  0 skips**, 116.162 s. No environment/package activation. Private absolute
  checkout components are intentionally omitted from this report.
- Owner-run Windows: `python -I -S -B data/research/trading_intelligence_v2/v26c_native_check.py --check`:
  **11 checks, 0 failures, 0 errors, 0 skips**.
- Owner-run Windows: same entry point `--session-check`: **25 checks,
  0 failures, 0 errors, 0 skips**. Both native commands deny all sockets and
  operational imports; the latter allows only the fixed synthetic worker argv.
- Owner-run Windows `--negative-security-check`: **3 checks, 0 failures,
  0 errors, 0 skips** against a real junction and a newly created empty broad-ACL
  fixture. The two fixtures were removed afterwards; archive ACLs were unchanged.
  Total final executions: **737 checks, 0 failures, 0 errors, 0 skips**.

Eight unchanged isolated Windows regression commands passed **556 tests,
0 failures, 0 errors, 0 skips**:

- `python -I -S -B data/research/trading_intelligence_v2/v26b_run.py --tests`: 46.
- `python -I -S -B data/research/trading_intelligence_v2/v26_run.py --tests`: 99.
- `python -I -S -B data/research/trading_intelligence_v2/v25_run.py --v25-tests`: 78.
- `python -I -S -B data/research/trading_intelligence_v2/v24_run.py --v24-tests`: 73.
- `python -I -S -B data/research/trading_intelligence_v2/run.py --v23-tests`: 58.
- `python -I -S -B data/research/trading_intelligence_v2/run.py --mtf-tests`: 73.
- `python -I -S -B data/research/trading_intelligence_v2/run.py --tests`: 72.
- `python -I -S -B offline_exposure/run_checks.py`: 57.

## Coverage and limits

Archive cases cover exact native root, owner/ACL/pin checks, missing/root refusal,
OneDrive/repository refusal, traversal/device/reparse/hardlink refusal, identity
mismatch, atomic/no-clobber publication, hash mismatch and interrupted pending
files. Windows portable reparse unit case uses a mocked junction predicate;
POSIX creates a real symlink. Separate native checks reject a real Windows
junction handle/path and a broad DACL. Native identity handles and replacement
refusal are exercised on Windows, not claimed from Ubuntu coverage.

Budget cases cover missing/corrupt/type-invalid journal, absent/mismatched grant,
durable claim/reservation, duplicate reservation, two actual worker processes,
all seven crash points, restart refusal and no authorisation/reset transitions.
Deadline cases cover preparation, reservation, connection, headers, body,
validation, archive publication and final persistence, worker exit, fencing
unavailable and no ambiguity retry. Network cases exercise the unchanged V2.6
transport with one-attempt fixtures, fixed GET/host/path/parameters,
headers/proxy/redirect refusal, valid/malformed/boundary responses and redaction.
Audit hooks deny actual sockets, broker imports and production-state files.
Authenticated requests: **0**; API-host probes: **0**.

Limits: real TLS/header/body blocking, hard real-time OS guarantees and an
authenticated credential/native-grant bridge are not established by fixtures.
No actual real grant is created. These are readiness gaps, not skipped tests.

## Development failures, retained honestly

Initial 59-test Windows run: **34 failures, 4 errors, 0 skips**. A repeat captured
the same result. Four subsequent harness-debug runs each had **35 failures,
0 errors, 0 skips**. Fixed Windows command-line audit representation, null-device
allowlisting, read-only fsync and preloaded test-only socket/mock imports;
no network restriction was removed. Then 59, 64 and 68-test iterations passed
on Windows; 64 and 68 also passed on Ubuntu. Final 71-test runs passed on both.

The initial native handle-replacement test raised one assertion because the
metadata-only handle permitted rename. The directory was restored immediately;
FILE_LIST_DIRECTORY fixed the sharing semantics. Subsequent native checks passed.
No unrelated source, test assertion or operational seal was changed to pass.

## CI

Adds one isolated stdlib Ubuntu job, without hiding/changing the full suite.
Baseline V2.6B hosted run 40553263428: all eight feature jobs passed; full suite
failed with **300 failed, 2789 passed, 64 skipped, 144 errors** (127 warnings).
The 444 failure/error identities are the comparison baseline. Final publication
and hosted conclusions must be reported separately; local passing suites do not
make overall CI green. Unrestricted full-suite execution is not run locally.

No V2.6C commit/push or new hosted run: authenticated integration and actual TLS
deadline verification are incomplete. The new workflow job remains a reviewed
local proposal; no existing job was hidden or disabled.

One filesystem-boundary limitation is outside the passing tests: a final
unscoped `git diff --name-only` displayed no contents, but may have caused Git
to read modified scheduler files internally. Those contents were not inspected
or emitted, and no scheduler file was changed. Strict no-content-read compliance
cannot be certified. Publication remains held for this reason as well.
