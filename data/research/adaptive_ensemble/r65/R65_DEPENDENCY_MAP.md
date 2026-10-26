# R.65 dependency map

## Operational

`main.py` imports `uvicorn` and `forex_bot.alerts`. The application object is `forex_bot.app:app`. `app.py` imports `forex_bot.bot_loop.run_bot`. The loop can import `forex_bot.v2_shadow` for record-only observation. That package uses thread locks around files. It does not import the diagnostic supervisor or the R.62–R.64 packages.

`forex_bot` process-API scan: `subprocess` appears in `shadow/manifest.py` and `research/adaptive_ensemble/g4_integrity.py`. Both call `git`. Neither is the diagnostic worker and neither is referenced by `bot_loop`.

## Diagnostic research

R.61 tests load `diagnostic_supervisor.py` by path. The supervisor `Popen`s `diagnostic_worker.py`. The worker's `_load` stems are the literals `credential_ipc`, `live_session_gate`, `restricted_live_transport`, and `metadata_extract`. R.59 and R.60 do the same inside their own directories. R.56 phase 6 is an earlier copy with its own tests.

Dynamic import in the worker cannot name an R.62, R.63, or R.64 module unless the worker source changes. The eligibility manifest hashes that source so such a change drops eligibility.

## Research-only containment

R.62, R.63, and R.64 import only siblings inside their `poc` directories, plus the standard library and, on Windows, `kernel32`. A repository search for those package names and for `ProcessLifecycleManager`, `win_containment`, and `cgroup_lifecycle` hits only those `poc` trees.

## Test-only

Each stage's pytest file is the caller. `pytest` is not an operational entry. This stage did not run `main.py`.

## Boundary

`RESEARCH_IMPLEMENTATIONS_NOT_INTEGRATED`

`R65_RESEARCH_OPERATIONAL_BOUNDARY_VERIFIED`
