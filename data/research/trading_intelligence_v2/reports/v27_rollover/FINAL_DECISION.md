# Read-isolation correction: local verification complete, renewed approval required

The previous publication attempt stopped correctly. Although all 215 old tests passed, the namespaced worker retained legacy authority paths and could read PACKAGE fixture state. The correction replaces the allowlist and removes the broad package-data exception. Actual child-process file opens, writes and substitutions now prove denial for legacy and sibling records, junctions and hardlinks, while own-session and explicitly documented shared resources remain readable.

All 220 focused tests passed without failures or skips. Global exclusion, durable reservation, session-bound single-use authority, UNKNOWN preservation, request restrictions and 15/120/15-second timing remain unchanged. No other runtime authority/controller code was altered relative to the superseded reviewed implementation.

The exact proposed publication scope remains 17 files: eight source/runner files (direct_history.py, oneshot.py, oneshot_archive.py, oneshot_authorisation.py, oneshot_response.py, oneshot_worker.py, session_namespace.py, v26d_run.py), three tests (test_v26g.py, test_v27_activation.py, test_v27_rollover.py), reports/v27_activation/source_seal.json and the five required v27_rollover reports. Corrected hashes and complete/delta diffs are provided separately for review. The prior approval does not apply to these new bytes.

Only those 17 corrected files are staged for review. No commit or push occurred; HEAD remains 8ecadc8650d0a4abfd521ee2013a24dc69380b6d. Credentials, grants, journals, market data, local proposal/backups and unrelated scheduler changes are excluded. Operational code, R.56, frozen strategies and local data are unchanged. Scheduler operation is preserved.

Corrected runtime seal: 39bd36d8a7f7b6abb7bbbcb28739bb39f1fb75d80a779fa2809ba59252d7ab9e. The preserved c202998c655f4af7b066a31f9636aed6 proposal is now stale and non-authorising. No namespace was reset or replaced, and no executable LIVE grant, real credential access, OANDA call or trading activation occurred.

Stop here for renewed publication review. Git publication and any later exact authenticated GET require separate explicit approvals. Production trading remains NO-GO.
