# V2.6F focused tests — 2026-10-28

Windows Python 3.13, isolated -I -S -B; repository baseline 5061ad4.
All commands exited 0; zero failures, errors or skips. No full historical suite
was rerun locally. No runtime or historical test changes were necessary.

1. `python -I -S -B data/research/trading_intelligence_v2/v26d_run.py --native-v26e-tests`
   — 50 tests, 28.802 seconds. Synthetic credentials and local HTTPS only, with
   the existing protected external native-storage binding.
2. `python -I -S -B data/research/trading_intelligence_v2/v26c_native_check.py --check`
   — 11 native storage checks. This existing checker publishes explicitly
   synthetic test artifacts externally; it does not alter genuine data or bindings.
3. An ephemeral stdin unittest harness (`python -I -S -B -`) — 2 tests, 5
   subcases: request_guard rejects explicit HTTP, HTTPS and SOCKS proxy values;
   Archive(root) with synthetic=False rejects both the repository root and a
   separate OneDrive ResearchArchive path with APPROVED_ROOT_REQUIRED, before
   opening or creating either destination. No harness was added to the repository.

Coverage of the 22 requested readiness checks:

- 1–3: test_v26e.ExistingClientContract verifies existing-client AST and exact
  live host/path/query against SPEC (test_v26e.py:24, :50).
- 4–7: foreign-routes test rejects account, order, trade and position-close paths
  (test_v26e.py:63); no requests are dispatched for these candidates.
- 8–9: inherited test_redirect verifies one refusal with no follow; sensitive
  metadata/proxy rejection and the explicit proxy harness reject substitution.
- 10–11: disabled-provider, provider-error-redaction and worker argv/environment/
  archive-content tests use synthetic values. AST/audit controls exclude dotenv,
  operational imports and private configuration; no actual credential source was accessed.
- 12–14: test_provider_called_after_durable_reservation,
  test_two_process_https_race and consumed() exercise the existing worker
  processes under one archive lock. One completes, the competing worker refuses;
  restarted consumed state refuses without a second connection.
- 15–17: delayed TLS/headers/body, dispatch stall, HTTP 401/403/404/429/500 and
  all crash-phase tests check fencing, elapsed budget, consumption and no retry.
- 18: native mode holds the current protected binding. The 11-check native run
  verifies fixed NTFS identity/owner+SYSTEM ACLs, handles preventing replacement,
  safe paths, hash/atomic publication and immutable writes.
- 19–20: explicit real-archive wrong-root tests reject OneDrive and Git roots.
  Portable synthetic fixture storage in Git's ignored outputs is test-only and
  does not establish permission to publish real data there.
- 21–22: no operational module in sys.modules; external connect and even
  getaddrinfo(api-fxtrade.oanda.com,443) are denied by the test audit policy
  before network activity (test_v26d.py:181–188). Only local synthetic HTTPS ran.

The exact live-host test validates schema selection, not real connectivity.
No future external-DNS/real-provider branch exists to test. Permission and
entitlement findings are documentary and remain unresolved.

Git review: only five V26F Markdown reports are intended for staging. Preserve
the pre-existing scheduler/operator_attention.jsonl modification and all ignored
runtime/private data. Exact pushed SHA and hosted CI conclusions are supplied in
the delivery message after publication; this report does not predeclare CI green.
