# R56_CAPABILITY_REDEMPTION_FIX_REPORT

Overall: **PASS**

`CAPABILITY_MODE_REDEMPTION_VERIFIED_OFFLINE`

`REAL_DISPATCH_CONTRACT_VERIFIED`

`REAL_NETWORK_EXECUTION_NOT_TESTED`

`REAL_SESSION_SOURCE_ENABLEMENT` remains `False`. No OANDA connection was opened. No real credential was read. The production bot was not started. A real OANDA session was not executed.

## Root cause

`_spawn_authenticated` issued a capability with `mode=contract["capability_mode"]`, then redeemed it with the hardcoded mode `HARNESS_SESSION`. A token bound to `REAL_SESSION` cannot be redeemed as `HARNESS_SESSION`, so the real dispatch would fail closed at the handshake even after a future source-gate change.

## Code change

The spawn now calls `redeem_for_dispatch`. That function checks `assert_dispatch_consistent` and passes `contract["capability_mode"]` to `issuer.redeem`. The child does not supply the mode. A missing or inconsistent mode raises `MODE_REJECTED` or `MODE_MISMATCH` before redemption.

`issue(mode="REAL_SESSION")` still calls `assert_real_session` and was not given a bypass. Offline real-mode checks use `issue_offline_mode_binding` on a local issuer. Those tokens set `authorises_network` false. The spawn path does not call that method. The fixture issuer is expired at the end of the test.

## Redemption results

- Harness issue and harness redemption through `redeem_for_dispatch` succeeded once. The second call was `CAPABILITY_REPLAYED`.
- A local offline binding for `REAL_SESSION` redeemed with the real dispatch contract. Redemption with the harness contract was `GRANT_REJECTED`. The source switch stayed false and `real_connections_opened` stayed 0.
- A harness capability redeemed with the real contract was `GRANT_REJECTED`.
- Forgery was `CAPABILITY_FORGED`. Expiry was `CAPABILITY_EXPIRED`. The wrong session was `CAPABILITY_WRONG_SESSION`. The wrong step was `CAPABILITY_WRONG_STEP`.
- The real contract's capability mode is `REAL_SESSION` for both the contract and the redemption that succeeded. The harness contract's mode is `HARNESS_SESSION` for both. A hardcoded harness mode in the shared redemption helper would fail the real-contract redemption.

## Subprocess regression

The existing harness session still completed two synthetic GETs, withheld pricing after summary HTTP 500, killed and reaped a stalled child, and rejected a third budget reservation. No retry ran. `socket.getaddrinfo` stayed blocked.

## Tests

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase6_connection_enablement/test_phase6_offline.py`

**15 passed, 0 failed, 0 skipped, 7.23 s.**

New test: `test_capability_redemption_follows_the_dispatch_mode`.

## Files changed

- `diagnostic_supervisor.py`
- `live_session_gate.py`
- `test_phase6_offline.py`
- `02_request_and_credential_security.md`
- `04_test_results.md`
- `06_integrity_manifest.json` (regenerated after this report)
- `11_capability_redemption_fix.md` (this file)

## Source hashes

- `restricted_live_transport.py` `3df6be9b1422ac52f12a8961cc31b079db4b978b6e0ad27f304d1503f5d545e0` (unchanged)
- `credential_ipc.py` `77547f55ba5bc038eac04147de76dcdc8ba3701ab0aefe6258ff1a713b54fa4a` (unchanged)
- `live_session_gate.py` `ae07d4ca969c8696215510a059e7c5c9e6d66933834b3117080e21207bfeee9a`
- `diagnostic_worker.py` `59afcac36a67ea210699ce8ea91283f8c9e4cb0f5ceef309f0a40a3525078022` (unchanged)
- `diagnostic_supervisor.py` `6556d0273cfa9884a153ec0e72e16ce09c9a691c72844c2a6ace881133f2f14e`
- `offline_entry.py` `dc00f6b20efd1c02e4c795aae3f794222c58f71582acc55f25dde6797ff54100` (unchanged)
- `test_phase6_offline.py` `360d8101f09cd34f6a8d38eb400167fe0e8a74ea42654ead35571dd629e29ae8`

## Git integrity

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. No commit, reset, clean, stash, or checkout was run. The previous review ZIP was not overwritten.

## Confirmations

- The source gate remains `False`.
- No real credential was entered, read, or requested.
- No OANDA Live or Practice connection was made.
- The production bot remained stopped.
- No unresolved blocker.
- Production deployment remains NO-GO.
