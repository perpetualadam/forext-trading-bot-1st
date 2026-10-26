# STAGE R.55 — BOUNDARY B1 FINAL ACTIVATION BUILD RETRY REPORT

Historical record. The executable hash named below has been superseded. It does not authorise a live session.

Classification: `R55_B1_FINAL_ACTIVATION_BUILD_PREPARED`

The offline session passed and the real transport is implemented. This classification does not authorise the live command, and it does not verify the account.

## Branch and HEAD

- Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`
- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Working tree: dirty, and left dirty.

## Preservation

R.24 through R.55 Boundary A evidence is present. Operational source hashes match. Source text shows all six strategies inactive, the quant stub returning `quant_stub_removed`, and unverified RL returning `UNAVAILABLE`. Research lifecycle code is not referenced by `bot_loop.py` or `ai_ensemble.py`. No production trading module was imported.

## Authoritative hashes

| File | SHA-256 |
| --- | --- |
| R.51 `https_adapter.py` | `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef` |
| R.52 `session_entry.py` | `59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56` |
| R.53 `connector.py` | `7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4` |
| R.54 `session_main.py` | `50d2dfd2b3c7e2909994e7ccbebfd30d7c50021e8a2a8f70df5f11d78b880280` |
| R.55 Boundary A `session_main.py` | `5913a190812343a9039570893f6cc96fb30fb2a08a6305b84e0bb7bea3576cf8` |

The R.52 value is the authoritative pin. All five matched. Those files were not edited.

## New executable

`data/research/adaptive_ensemble/r55/b1/session_main.py`

SHA-256: `11b761ae8091352e5b1a30ab9f3682b5f005006a665659e1fa86f9d4aad545a6`

Imported transport `data/research/adaptive_ensemble/r55/b1/transport.py`

SHA-256: `ee01779fbcad9cecc8c9a24f0502ce4f3499c83a8a10a09d8fb1390e6c797367`

Also imported: R.53, R.50 `connector.py`, R.48 `readonly_transport.py`, and R.50 `fixtures.py`. R.51, R.52, R.54, and the Boundary A session are hash-checked only.

## Credential and network status

Real credentials were not accessed. No authenticated request was sent. No DNS lookup and no external connection were made. `run_live` was not called. The default command prints `R55 B1 default entry is disabled. No credential prompt. No network connection.`

## Offline tests

Attempt 1 failed during test collection because the fixture path was one directory high. No security assertion ran. The path was corrected.

Attempt 2: 8 passed, 0 failed.

The success path recorded 2 attempted, 2 HTTP successes, and 2 validated, in order: instruments then pricing. A malformed first body stayed at 1 / 1 / 0. A failed first HTTP response stayed at 1 / 0 / 0. Timeout, TLS failure, and redirect did not retry. An unexpected instrument stopped before pricing. A refused confirmation made no credential request.

## Security and review

All 51 behaviours passed on attempt 2. The local review found no hidden live switch, no order method, no production import, and no unresolved blocker. Details are in `07_security_tests.md` and `10_source_dependency_review.md`.

## Sanitised output

`06_synthetic_output.json` is marked `SYNTHETIC_TEST_ONLY`. It contains no token, account identifier, authorization header, full URL, `1.35` fallback, or executable size. Account home currency remains `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`. The synthetic USD/JPY spread is 3 pips from pip location `-2`. This file is not broker data.

## Manual procedure

`data/research/adaptive_ensemble/r55/b1/09_manual_procedure.md`

## Remaining blockers

Boundary B2 is not approved. Home currency, spread-bet stake meaning, and token permission remain unknown. No executable size is available.

## Boundary B2 approval requirements

Do not begin R.56. A real session needs a separate written approval that names executable hash `11b761ae8091352e5b1a30ab9f3682b5f005006a665659e1fa86f9d4aad545a6`. Until that approval, the live command must not be typed. The future session, if approved, is one Start-menu Windows Terminal run: preview, local confirmation, account identifier, hidden token, then the two GET requests only. Orders, candles, backtests, strategy activation, deployment, and rollback stay excluded.

PRODUCTION DEPLOYMENT: NO-GO.

PRACTICE ORDERS: NOT AUTHORISED.

LIVE TRADING: NOT AUTHORISED.

ROLLBACK: NO-GO.
