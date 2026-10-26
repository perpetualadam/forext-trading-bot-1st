# D.7 regression compatibility

D.2 preservation, D.3 activation defaults, and D.4 startup-preflight tests passed: 30, 35, and 50. They do not import `app.py`.

The unmodified D.5 runner was executed by the D.7 suite and returned exit 0. Valid BLOCKED still yields. Corrupt state still raises `StartupSafetyAbort` before the fake `get_connection` and `build_api`. The D.5 pytest module itself errors in setup because it pins the pre-D.7 `app.py` hash. That file was not edited.

The D.6 pytest module errors on the same frozen hash, so its leak assertions did not run. Those assertions still expect the old defects: database failures leave `close_calls == 0`, fatal startup leaves the connection held, and task or shutdown failures leave tasks pending for the harness to cancel. They would fail if the hash pin were removed. They were not rewritten. D.7 tests cover the corrected behaviour. Full D.6 pytest compatibility is not claimed.

The repair module returned exit 0 under the D.7 guard process, with an empty network list. Order-routing functions were not wrapped in that mode.

Account-summary and reconciliation failures still yield and still cancel four tasks on shutdown. A successful startup still yields with authorisation BLOCKED and all six strategies inactive. A successful shutdown cancels the four tasks and does not close the process-global connection.
