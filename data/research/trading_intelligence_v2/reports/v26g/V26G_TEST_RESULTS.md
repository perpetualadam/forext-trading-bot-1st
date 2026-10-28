# V2.6G focused and regression results — 2026-10-28

Windows Python 3.13; established isolated -I -S -B runners. Final Windows results
below all exited 0, with no failures/errors/skips. No operational trading loop,
real getter, .env, Credential Manager or API-host probe was used.

- v26d_run.py --v26g-tests: **67**, 33.642 seconds, portable Windows.
- v26d_run.py --native-v26g-tests: **67**, 32.397 seconds, protected native Windows.
- v26d_run.py --v26g-tests under local Ubuntu /usr/bin/python3: **67**,
  116.552 seconds, exit 0; synthetic HTTPS only.
- v26d_run.py --v26e-tests: **50**, exit 0.
- v26d_run.py --tests: **38**, exit 0.
- v26c_run.py --tests: **71**, exit 0.
- v26b_run.py --tests: **46**, exit 0.
- v26_run.py --tests: **99**, exit 0.
- v25_run.py --v25-tests: **78**, exit 0.
- v24_run.py --v24-tests: **73**, exit 0.
- managed_run.py --v23-tests: **58**, exit 0.
- managed_run.py --mtf-tests: **73**, exit 0.
- managed_run.py --tests: **72**, exit 0.
- offline_exposure/run_checks.py: **57**, exit 0.
- v26c_native_check.py --check: **11 checks**, exit 0.
- v26c_native_check.py --session-check: **25 checks**, exit 0.
- v26c_native_check.py --negative-security-check: **3 checks**, exit 0.

V2.6F relevant checks are covered by the same native HTTPS suite plus explicit
proxy/OneDrive/repository-root refusal tests. No separate V2.6F runner exists.

The first development run (63 tests) exited 1 with three failures because the
shared transport hid TLS/connection exception types. The implementation boundary
was corrected; historical assertions were not changed. Intermediate 64-case
portable/native runs and subsequent 65/67-case runs passed. No failure is omitted from
the final interpretation. The final Linux run also passed all 67 tests.

Coverage of required checks 1–30:

- 1–3: permanently refusing admission tested with absent, fabricated and copied
  inputs while getters/DNS/socket constructors are patched to fail if called.
- 4–12: inherited V2.6E exact method/host/path/instrument/query tests reject all
  account/order/trade/position-close alternatives without dispatch.
- 13–16: inherited redirect/TLS refusal plus explicit proxy, public IPv4/IPv6,
  DNS-name/port/address/family/scope and single-connect tests. Public IP literals
  in unit tests are fake records; no connection is made to them.
- 17–20: synthetic getter and exception-redaction tests; real-provider body runs
  with a synthetic getter only after observing REQUEST_RESERVED and claimed grant;
  existing bounded IPC, TLS worker, credential-echo refusal and token-free archive.
- 21–25: unchanged two-process race, seven crash phases, consumed restart, timeout,
  worker fence and no-repeat assertions through the shared exchange.
- 26–27: protected NTFS identity/ACLs, atomic publication, immutable writes and
  receipt/raw/validated hashes; native junction and broad-ACL refusal checks.
- 28–30: source-only operational audit, no production import/state access,
  API-host DNS/connect refused before network and no actual token source queried.

The three negative fixtures were confirmed absent, created empty at their exact
pre-existing checker paths, and removed nonrecursively. The deliberately broad
ACL applied only to the empty disposable negative fixture, never the archive root.
Existing bindings/ACL implementation and genuine local data were preserved.

Limitations: DNS/SNI/real connector unit tests use fake sockets; the real admission
gate is replaced only in narrowly scoped synthetic tests. Physical end-to-end
tests remain local HTTPS, not OANDA. Supervisor reservation-before-worker-start and one-use worker claim use
explicit memory doubles; real admission is not represented as a passing live test.

A focused offline-only CI job is proposed locally alongside all existing jobs.
No V2.6G commit/push/hosted CI run exists. Published baseline f8eabd4 has green
14-job CI; that is separate from the local results above. See source hashes and
exact local review patch; do not publish security-sensitive code without approval.
